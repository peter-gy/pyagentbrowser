#[cfg(windows)]
use std::net::{SocketAddr, TcpListener, TcpStream};
#[cfg(unix)]
use std::os::unix::net::{UnixListener, UnixStream};
use std::{
    fs,
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

use serde_json::{Value, json};

#[cfg(test)]
mod tests;

use super::cleanup_dashboard_sidecar_files;
#[cfg(windows)]
use super::write_dashboard_text_file;

pub(super) struct ControlBridge {
    shutdown: Arc<AtomicBool>,
    done: Arc<AtomicBool>,
    handle: Option<thread::JoinHandle<()>>,
    wake: ControlWake,
}

const CONTROL_BRIDGE_READ_TIMEOUT: Duration = Duration::from_millis(250);
const CONTROL_BRIDGE_WRITE_TIMEOUT: Duration = Duration::from_millis(250);
const CONTROL_BRIDGE_JOIN_TIMEOUT: Duration = Duration::from_millis(750);
const CONTROL_BRIDGE_MAX_REQUEST_BYTES: u64 = 16 * 1024;

#[derive(Clone)]
enum ControlWake {
    #[cfg(unix)]
    Unix(PathBuf),
    #[cfg(windows)]
    Tcp(SocketAddr),
}

impl Drop for ControlBridge {
    fn drop(&mut self) {
        self.shutdown.store(true, Ordering::SeqCst);
        wake_control_bridge(&self.wake);
        if let Some(handle) = self.handle.take() {
            let deadline = Instant::now() + CONTROL_BRIDGE_JOIN_TIMEOUT;
            while !self.done.load(Ordering::SeqCst) && Instant::now() < deadline {
                thread::sleep(Duration::from_millis(10));
                wake_control_bridge(&self.wake);
            }
            if self.done.load(Ordering::SeqCst) {
                let _ = handle.join();
            }
        }
    }
}

#[cfg(unix)]
pub(super) fn start_control_bridge(dir: &Path, session_id: &str) -> Result<ControlBridge, String> {
    let socket_path = dir.join(format!("{session_id}.sock"));
    if socket_path.exists() {
        if UnixStream::connect(&socket_path).is_ok() {
            return Err(format!(
                "session '{session_id}' already has an active agent-browser control socket"
            ));
        }
        let _ = fs::remove_file(&socket_path);
    }
    let listener = UnixListener::bind(&socket_path).map_err(|err| {
        format!(
            "failed to bind dashboard control socket '{}': {err}",
            socket_path.display()
        )
    })?;
    listener
        .set_nonblocking(true)
        .map_err(|err| format!("failed to configure dashboard control socket: {err}"))?;
    let shutdown = Arc::new(AtomicBool::new(false));
    let done = Arc::new(AtomicBool::new(false));
    let thread_shutdown = Arc::clone(&shutdown);
    let thread_done = Arc::clone(&done);
    let thread_session = session_id.to_string();
    let thread_dir = dir.to_path_buf();
    let handle = thread::spawn(move || {
        run_control_loop(listener, thread_shutdown, thread_session, thread_dir);
        thread_done.store(true, Ordering::SeqCst);
    });
    Ok(ControlBridge {
        shutdown,
        done,
        handle: Some(handle),
        wake: ControlWake::Unix(socket_path),
    })
}

#[cfg(windows)]
pub(super) fn start_control_bridge(dir: &Path, session_id: &str) -> Result<ControlBridge, String> {
    let port_path = dir.join(format!("{session_id}.port"));
    if let Ok(port) = fs::read_to_string(&port_path)
        && let Ok(port) = port.trim().parse::<u16>()
        && TcpStream::connect(("127.0.0.1", port)).is_ok()
    {
        return Err(format!(
            "session '{session_id}' already has an active agent-browser control port"
        ));
    }
    let _ = fs::remove_file(&port_path);
    let listener = TcpListener::bind(("127.0.0.1", 0))
        .map_err(|err| format!("failed to bind dashboard control port: {err}"))?;
    listener
        .set_nonblocking(true)
        .map_err(|err| format!("failed to configure dashboard control port: {err}"))?;
    let address = listener
        .local_addr()
        .map_err(|err| format!("failed to resolve dashboard control port: {err}"))?;
    write_dashboard_text_file(dir, session_id, "port", &address.port().to_string())?;
    let shutdown = Arc::new(AtomicBool::new(false));
    let done = Arc::new(AtomicBool::new(false));
    let thread_shutdown = Arc::clone(&shutdown);
    let thread_done = Arc::clone(&done);
    let thread_session = session_id.to_string();
    let thread_dir = dir.to_path_buf();
    let handle = thread::spawn(move || {
        run_control_loop(listener, thread_shutdown, thread_session, thread_dir);
        thread_done.store(true, Ordering::SeqCst);
    });
    Ok(ControlBridge {
        shutdown,
        done,
        handle: Some(handle),
        wake: ControlWake::Tcp(address),
    })
}

fn run_control_loop<L, S>(
    listener: L,
    shutdown: Arc<AtomicBool>,
    session_id: String,
    socket_dir: PathBuf,
) where
    L: ControlListener<Stream = S>,
    S: ControlStream,
{
    while !shutdown.load(Ordering::SeqCst) {
        match listener.accept_control() {
            Ok(stream) => handle_control_stream(stream, &socket_dir, &session_id),
            Err(err) if err.kind() == std::io::ErrorKind::WouldBlock => {
                thread::sleep(Duration::from_millis(25));
            }
            Err(_) => break,
        }
    }
}

trait ControlListener {
    type Stream: ControlStream;

    fn accept_control(&self) -> std::io::Result<Self::Stream>;
}

trait ControlStream: Read + Write {
    fn set_control_timeouts(&self) -> std::io::Result<()>;
}

#[cfg(unix)]
impl ControlListener for UnixListener {
    type Stream = UnixStream;

    fn accept_control(&self) -> std::io::Result<Self::Stream> {
        self.accept().map(|(stream, _)| stream)
    }
}

#[cfg(unix)]
impl ControlStream for UnixStream {
    fn set_control_timeouts(&self) -> std::io::Result<()> {
        self.set_read_timeout(Some(CONTROL_BRIDGE_READ_TIMEOUT))?;
        self.set_write_timeout(Some(CONTROL_BRIDGE_WRITE_TIMEOUT))
    }
}

#[cfg(windows)]
impl ControlListener for TcpListener {
    type Stream = TcpStream;

    fn accept_control(&self) -> std::io::Result<Self::Stream> {
        self.accept().map(|(stream, _)| stream)
    }
}

#[cfg(windows)]
impl ControlStream for TcpStream {
    fn set_control_timeouts(&self) -> std::io::Result<()> {
        self.set_read_timeout(Some(CONTROL_BRIDGE_READ_TIMEOUT))?;
        self.set_write_timeout(Some(CONTROL_BRIDGE_WRITE_TIMEOUT))
    }
}

fn handle_control_stream<S: ControlStream>(mut stream: S, socket_dir: &Path, session_id: &str) {
    let _ = stream.set_control_timeouts();
    let mut line = String::new();
    {
        let mut reader = BufReader::new(&mut stream);
        let _ = reader
            .by_ref()
            .take(CONTROL_BRIDGE_MAX_REQUEST_BYTES)
            .read_line(&mut line);
    }
    let action = serde_json::from_str::<Value>(&line)
        .ok()
        .and_then(|cmd| {
            cmd.get("action")
                .and_then(Value::as_str)
                .map(ToOwned::to_owned)
        })
        .unwrap_or_else(|| "unknown".to_string());
    let response = if is_dashboard_detach_action(&action) {
        cleanup_dashboard_sidecar_files(socket_dir, session_id);
        json!({
            "success": true,
            "data": {
                "observable_only": true,
                "detached": true,
                "action": action,
            },
        })
    } else {
        json!({
            "success": false,
            "error": format!(
                "Session '{session_id}' is owned by pyagentbrowser and is observable-only in the dashboard. Use the Python Browser object for control commands"
            ),
            "data": {
                "observable_only": true,
                "action": action,
            },
        })
    };
    if let Ok(mut response_line) = serde_json::to_string(&response) {
        response_line.push('\n');
        let _ = stream.write_all(response_line.as_bytes());
        let _ = stream.flush();
    }
}

fn is_dashboard_detach_action(action: &str) -> bool {
    matches!(action, "close" | "quit" | "exit")
}

fn wake_control_bridge(wake: &ControlWake) {
    match wake {
        #[cfg(unix)]
        ControlWake::Unix(path) => {
            let _ = UnixStream::connect(path);
        }
        #[cfg(windows)]
        ControlWake::Tcp(address) => {
            let _ = TcpStream::connect(address);
        }
    }
}
