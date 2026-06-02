#[cfg(unix)]
use std::os::unix::net::UnixListener;
use std::{
    collections::HashSet,
    env, fs,
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

use agent_browser::native::{
    actions::{DaemonState, execute_command},
    network::DomainFilter,
    policy::{ActionPolicy, ConfirmActions},
};
use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
};
use serde::Deserialize;
use serde_json::{Value, json};
use tokio::{
    runtime::{Builder, Runtime},
    sync::RwLock,
};

mod skill_data {
    include!(concat!(env!("OUT_DIR"), "/pyagentbrowser_skill_data.rs"));
}

#[pyclass(name = "NativeBrowser", module = "pyagentbrowser._native")]
struct PyNativeBrowser {
    state: Mutex<DaemonState>,
    runtime: Runtime,
    dashboard: Mutex<Option<DashboardSidecar>>,
}

#[derive(Default, Deserialize)]
struct NativeBrowserOptions {
    session: Option<String>,
    session_name: Option<String>,
    default_timeout_ms: Option<u64>,
    allowed_domains: Option<String>,
    engine: Option<String>,
    action_policy: Option<String>,
    confirm_actions: Option<Vec<String>>,
    no_auto_dialog: Option<bool>,
    dashboard: Option<DashboardOption>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum DashboardOption {
    Enabled(bool),
    Config(DashboardConfig),
}

#[derive(Default, Deserialize)]
struct DashboardConfig {
    enabled: Option<bool>,
    port: Option<u16>,
    cli_version: Option<String>,
}

impl DashboardOption {
    fn into_config(self) -> Option<DashboardConfig> {
        match self {
            Self::Enabled(true) => Some(DashboardConfig {
                enabled: Some(true),
                port: None,
                cli_version: None,
            }),
            Self::Enabled(false) => None,
            Self::Config(config) if config.enabled.unwrap_or(true) => Some(config),
            Self::Config(_) => None,
        }
    }
}

#[pymethods]
impl PyNativeBrowser {
    #[new]
    #[pyo3(signature = (options_json=None))]
    fn new(py: Python<'_>, options_json: Option<&str>) -> PyResult<Self> {
        let options = match options_json {
            Some(raw) => serde_json::from_str::<NativeBrowserOptions>(raw).map_err(|err| {
                PyValueError::new_err(format!("invalid native options JSON: {err}"))
            })?,
            None => NativeBrowserOptions::default(),
        };
        let runtime = Builder::new_multi_thread()
            .enable_all()
            .thread_name("pyagentbrowser")
            .build()
            .map_err(|err| {
                PyRuntimeError::new_err(format!("failed to create tokio runtime: {err}"))
            })?;
        let mut state = native_state(&options)?;
        let dashboard = match options.dashboard.and_then(DashboardOption::into_config) {
            Some(config) => Some(start_dashboard(py, &runtime, &mut state, config)?),
            None => None,
        };

        Ok(Self {
            runtime,
            state: Mutex::new(state),
            dashboard: Mutex::new(dashboard),
        })
    }

    fn execute_json(&self, py: Python<'_>, command_json: &str) -> PyResult<String> {
        let command: Value = serde_json::from_str(command_json)
            .map_err(|err| PyValueError::new_err(format!("invalid command JSON: {err}")))?;

        if !command.is_object() {
            return Err(PyValueError::new_err("command JSON must be an object"));
        }
        let response = py
            .detach(|| {
                let mut state = self
                    .state
                    .lock()
                    .map_err(|_| "native browser state lock is poisoned".to_string())?;
                Ok::<Value, String>(
                    self.runtime
                        .block_on(async { execute_command(&command, &mut state).await }),
                )
            })
            .map_err(PyRuntimeError::new_err)?;
        let response = with_python_error_code(response);
        let should_shutdown_dashboard = command.get("action").and_then(Value::as_str)
            == Some("close")
            && response
                .get("success")
                .and_then(Value::as_bool)
                .unwrap_or(false);
        if should_shutdown_dashboard {
            py.detach(|| self.shutdown_dashboard())
                .map_err(PyRuntimeError::new_err)?;
        }

        serde_json::to_string(&response)
            .map_err(|err| PyRuntimeError::new_err(format!("failed to serialize response: {err}")))
    }
}

fn with_python_error_code(mut response: Value) -> Value {
    let Some(error) = response.get("error").and_then(Value::as_str) else {
        return response;
    };
    let code = if error.contains("Unknown ref:") {
        Some("unknown_ref")
    } else {
        None
    };
    if let Some(code) = code
        && let Some(object) = response.as_object_mut()
    {
        object.insert("code".to_string(), json!(code));
    }
    response
}

impl PyNativeBrowser {
    fn shutdown_dashboard(&self) -> Result<(), String> {
        let sidecar = self
            .dashboard
            .lock()
            .map_err(|_| "dashboard sidecar lock is poisoned".to_string())?
            .take();
        let Some(mut sidecar) = sidecar else {
            return Ok(());
        };

        {
            let mut state = self
                .state
                .lock()
                .map_err(|_| "native browser state lock is poisoned".to_string())?;
            if state.stream_server.is_some() {
                let cmd = json!({"id": "py-dashboard-disable", "action": "stream_disable"});
                let _ = self
                    .runtime
                    .block_on(async { execute_command(&cmd, &mut state).await });
            }
        }
        sidecar.cleanup();
        Ok(())
    }
}

impl Drop for PyNativeBrowser {
    fn drop(&mut self) {
        let _ = self.shutdown_dashboard();
    }
}

fn native_state(options: &NativeBrowserOptions) -> PyResult<DaemonState> {
    let mut daemon = DaemonState::new();
    if let Some(session) = &options.session {
        daemon.session_id.clone_from(session);
    }
    if let Some(session_name) = &options.session_name {
        daemon.session_name = Some(session_name.clone());
    }
    if let Some(default_timeout_ms) = options.default_timeout_ms {
        daemon.default_timeout_ms = default_timeout_ms;
    }
    if let Some(engine) = &options.engine {
        daemon.engine.clone_from(engine);
    }
    if let Some(action_policy) = &options.action_policy {
        daemon.policy = Some(ActionPolicy::load(action_policy).map_err(PyValueError::new_err)?);
    }
    if let Some(confirm_actions) = &options.confirm_actions {
        let categories: HashSet<String> = confirm_actions
            .iter()
            .map(|action| action.trim().to_lowercase())
            .filter(|action| !action.is_empty())
            .collect();
        daemon.confirm_actions = if categories.is_empty() {
            None
        } else {
            Some(ConfirmActions { categories })
        };
    }
    if let Some(allowed_domains) = &options.allowed_domains {
        daemon.domain_filter = Arc::new(RwLock::new(Some(DomainFilter::new(allowed_domains))));
    }
    if options.no_auto_dialog.unwrap_or(false) {
        daemon.auto_dialog = false;
    }
    Ok(daemon)
}

fn start_dashboard(
    py: Python<'_>,
    runtime: &Runtime,
    state: &mut DaemonState,
    config: DashboardConfig,
) -> PyResult<DashboardSidecar> {
    validate_dashboard_session_id(&state.session_id)?;
    let socket_dir = agent_browser::socket_dir();
    fs::create_dir_all(&socket_dir).map_err(|err| {
        PyRuntimeError::new_err(format!(
            "failed to create agent-browser socket directory '{}': {err}",
            socket_dir.display()
        ))
    })?;

    let mut sidecar = DashboardSidecar::new(state.session_id.clone(), socket_dir.clone());
    sidecar.control = Some(start_control_bridge(&socket_dir, &state.session_id)?);
    write_dashboard_text_file(
        &socket_dir,
        &state.session_id,
        "version",
        &dashboard_sidecar_version(config.cli_version.as_deref()),
    )?;
    let sentinel = spawn_dashboard_watchdog(py, &socket_dir, &state.session_id)?;
    let sentinel_pid = sentinel.id();
    sidecar.sentinel = Some(sentinel);
    write_dashboard_text_file(
        &socket_dir,
        &state.session_id,
        "pid",
        &sentinel_pid.to_string(),
    )?;
    write_dashboard_text_file(&socket_dir, &state.session_id, "engine", &state.engine)?;
    write_dashboard_text_file(
        &socket_dir,
        &state.session_id,
        "metadata",
        &json!({
            "owner": "pyagentbrowser",
            "control": "observable-only",
            "pid": sentinel_pid,
        })
        .to_string(),
    )?;

    let mut stream_cmd = json!({"id": "py-dashboard-enable", "action": "stream_enable"});
    if let Some(port) = config.port {
        stream_cmd["port"] = json!(port);
    }
    let stream_response = runtime.block_on(async { execute_command(&stream_cmd, state).await });
    if !stream_response
        .get("success")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        sidecar.cleanup();
        let message = stream_response
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("failed to start dashboard stream");
        return Err(PyRuntimeError::new_err(message.to_string()));
    }

    Ok(sidecar)
}

fn validate_dashboard_session_id(session_id: &str) -> PyResult<()> {
    if session_id.is_empty() || session_id.len() > 64 {
        return Err(PyValueError::new_err(
            "dashboard sessions require a 1-64 character session name",
        ));
    }
    if session_id.contains(['/', '\\', '\0']) {
        return Err(PyValueError::new_err(
            "dashboard session names must not contain path separators",
        ));
    }
    Ok(())
}

fn write_dashboard_text_file(
    dir: &Path,
    session_id: &str,
    extension: &str,
    content: &str,
) -> PyResult<()> {
    let path = dir.join(format!("{session_id}.{extension}"));
    fs::write(&path, content).map_err(|err| {
        PyRuntimeError::new_err(format!(
            "failed to write dashboard sidecar '{}': {err}",
            path.display()
        ))
    })
}

fn dashboard_sidecar_version(configured: Option<&str>) -> String {
    configured
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .or_else(|| {
            env::var("AGENT_BROWSER_DASHBOARD_CLI_VERSION")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty())
        })
        .unwrap_or_else(|| agent_browser::VERSION.to_string())
}

fn spawn_dashboard_watchdog(
    py: Python<'_>,
    socket_dir: &Path,
    session_id: &str,
) -> PyResult<Child> {
    let executable = py
        .import("sys")?
        .getattr("executable")?
        .extract::<String>()?;
    if executable.trim().is_empty() {
        return Err(PyRuntimeError::new_err(
            "cannot start dashboard watchdog because sys.executable is empty",
        ));
    }
    let parent_pid = std::process::id().to_string();
    Command::new(executable)
        .arg("-c")
        .arg(
            r#"import os, sys, time

parent_pid = int(sys.argv[1])
socket_dir = sys.argv[2]
session_id = sys.argv[3]
extensions = ("pid", "stream", "engine", "provider", "extensions", "version", "metadata", "port", "sock")

def cleanup():
    for extension in extensions:
        try:
            os.unlink(os.path.join(socket_dir, session_id + "." + extension))
        except FileNotFoundError:
            pass
        except OSError:
            pass

while True:
    if os.getppid() != parent_pid:
        cleanup()
        break
    try:
        os.kill(parent_pid, 0)
    except OSError:
        cleanup()
        break
    time.sleep(0.25)
"#,
        )
        .arg(parent_pid)
        .arg(socket_dir)
        .arg(session_id)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|err| {
            PyRuntimeError::new_err(format!("failed to start dashboard watchdog: {err}"))
        })
}

struct DashboardSidecar {
    session_id: String,
    socket_dir: PathBuf,
    sentinel: Option<Child>,
    control: Option<ControlBridge>,
    cleaned: bool,
}

impl DashboardSidecar {
    fn new(session_id: String, socket_dir: PathBuf) -> Self {
        Self {
            session_id,
            socket_dir,
            sentinel: None,
            control: None,
            cleaned: false,
        }
    }

    fn cleanup(&mut self) {
        if self.cleaned {
            return;
        }
        self.cleaned = true;
        drop(self.control.take());
        if let Some(mut sentinel) = self.sentinel.take() {
            let _ = sentinel.kill();
            let _ = sentinel.wait();
        }
        cleanup_dashboard_sidecar_files(&self.socket_dir, &self.session_id);
    }
}

impl Drop for DashboardSidecar {
    fn drop(&mut self) {
        self.cleanup();
    }
}

struct ControlBridge {
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
    Unix(PathBuf),
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

fn start_control_bridge(dir: &Path, session_id: &str) -> PyResult<ControlBridge> {
    let socket_path = dir.join(format!("{session_id}.sock"));
    if socket_path.exists() {
        if std::os::unix::net::UnixStream::connect(&socket_path).is_ok() {
            return Err(PyRuntimeError::new_err(format!(
                "session '{session_id}' already has an active agent-browser control socket"
            )));
        }
        let _ = fs::remove_file(&socket_path);
    }
    let listener = UnixListener::bind(&socket_path).map_err(|err| {
        PyRuntimeError::new_err(format!(
            "failed to bind dashboard control socket '{}': {err}",
            socket_path.display()
        ))
    })?;
    listener.set_nonblocking(true).map_err(|err| {
        PyRuntimeError::new_err(format!(
            "failed to configure dashboard control socket: {err}"
        ))
    })?;
    let shutdown = Arc::new(AtomicBool::new(false));
    let done = Arc::new(AtomicBool::new(false));
    let thread_shutdown = Arc::clone(&shutdown);
    let thread_done = Arc::clone(&done);
    let thread_session = session_id.to_string();
    let handle = thread::spawn(move || {
        run_control_loop(listener, thread_shutdown, thread_session);
        thread_done.store(true, Ordering::SeqCst);
    });
    Ok(ControlBridge {
        shutdown,
        done,
        handle: Some(handle),
        wake: ControlWake::Unix(socket_path),
    })
}

fn run_control_loop<L, S>(listener: L, shutdown: Arc<AtomicBool>, session_id: String)
where
    L: ControlListener<Stream = S>,
    S: ControlStream,
{
    let socket_dir = agent_browser::socket_dir();
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

impl ControlListener for UnixListener {
    type Stream = std::os::unix::net::UnixStream;

    fn accept_control(&self) -> std::io::Result<Self::Stream> {
        self.accept().map(|(stream, _)| stream)
    }
}

impl ControlStream for std::os::unix::net::UnixStream {
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
                "Session '{session_id}' is owned by pyagentbrowser and is observable-only in the dashboard; use the Python Browser object for control commands"
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

fn cleanup_dashboard_sidecar_files(socket_dir: &Path, session_id: &str) {
    for extension in [
        "pid",
        "stream",
        "engine",
        "provider",
        "extensions",
        "version",
        "metadata",
        "port",
        "sock",
    ] {
        let _ = fs::remove_file(socket_dir.join(format!("{session_id}.{extension}")));
    }
}

fn wake_control_bridge(wake: &ControlWake) {
    match wake {
        ControlWake::Unix(path) => {
            let _ = std::os::unix::net::UnixStream::connect(path);
        }
    }
}

#[pyfunction]
fn skill_data_json() -> &'static str {
    skill_data::SKILL_DATA_JSON
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyNativeBrowser>()?;
    m.add_function(wrap_pyfunction!(skill_data_json, m)?)?;
    m.add("__agent_browser_version__", agent_browser::VERSION)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{
        io::{Cursor, Read, Result as IoResult, Write},
        path::{Path, PathBuf},
    };

    use serde_json::{Value, json};

    use super::{ControlStream, cleanup_dashboard_sidecar_files, handle_control_stream};

    struct MemoryControlStream {
        input: Cursor<Vec<u8>>,
        output: Vec<u8>,
    }

    impl MemoryControlStream {
        fn new(input: &[u8]) -> Self {
            Self {
                input: Cursor::new(input.to_vec()),
                output: Vec::new(),
            }
        }
    }

    impl Read for MemoryControlStream {
        fn read(&mut self, buf: &mut [u8]) -> IoResult<usize> {
            self.input.read(buf)
        }
    }

    impl Write for MemoryControlStream {
        fn write(&mut self, buf: &[u8]) -> IoResult<usize> {
            self.output.write(buf)
        }

        fn flush(&mut self) -> IoResult<()> {
            Ok(())
        }
    }

    impl ControlStream for &mut MemoryControlStream {
        fn set_control_timeouts(&self) -> IoResult<()> {
            Ok(())
        }
    }

    fn control_response(socket_dir: &Path, session_id: &str, input: &[u8]) -> Value {
        let mut stream = MemoryControlStream::new(input);
        handle_control_stream(&mut stream, socket_dir, session_id);
        serde_json::from_slice(stream.output.as_slice()).expect("control response should be JSON")
    }

    fn unique_temp_dir(name: &str) -> PathBuf {
        let dir =
            std::env::temp_dir().join(format!("pyagentbrowser-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).expect("test directory should be created");
        dir
    }

    #[test]
    fn dashboard_control_rejects_invalid_json_and_non_detach_actions() {
        let socket_dir = unique_temp_dir("control-rejects");
        let session_id = "control-test";
        for (input, action) in [
            (b"{not-json\n".as_slice(), "unknown"),
            (br#"{"action":"navigate"}"#.as_slice(), "navigate"),
            (br#"{"action":"kill"}"#.as_slice(), "kill"),
            (br#"{"action":"screenshot"}"#.as_slice(), "screenshot"),
        ] {
            let response = control_response(&socket_dir, session_id, input);
            assert_eq!(response["success"], false);
            assert_eq!(response["data"]["observable_only"], true);
            assert_eq!(response["data"]["action"], action);
            assert!(
                response["error"]
                    .as_str()
                    .expect("error should be present")
                    .contains("observable-only")
            );
        }
        std::fs::remove_dir_all(socket_dir).expect("test directory should be removed");
    }

    #[test]
    fn dashboard_control_detach_actions_remove_sidecars() {
        let socket_dir = unique_temp_dir("control-detach");
        let session_id = "control-test";
        for action in ["close", "quit", "exit"] {
            for extension in [
                "pid", "stream", "engine", "provider", "metadata", "port", "sock",
            ] {
                std::fs::write(
                    socket_dir.join(format!("{session_id}.{extension}")),
                    "present",
                )
                .expect("sidecar file should be created");
            }

            let response = control_response(
                &socket_dir,
                session_id,
                format!(r#"{{"action":"{action}"}}"#).as_bytes(),
            );

            assert_eq!(
                response["data"],
                json!({
                    "observable_only": true,
                    "detached": true,
                    "action": action,
                })
            );
            for extension in [
                "pid", "stream", "engine", "provider", "metadata", "port", "sock",
            ] {
                assert!(
                    !socket_dir
                        .join(format!("{session_id}.{extension}"))
                        .exists()
                );
            }
        }
        cleanup_dashboard_sidecar_files(&socket_dir, session_id);
        std::fs::remove_dir_all(socket_dir).expect("test directory should be removed");
    }
}
