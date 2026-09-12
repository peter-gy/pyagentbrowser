use std::{
    path::Path,
    process::{Child, Command, Stdio},
};

pub(super) fn spawn_dashboard_watchdog(
    executable: &str,
    socket_dir: &Path,
    session_id: &str,
) -> Result<Child, String> {
    if executable.trim().is_empty() {
        return Err(String::from(
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

parent_handle = None
if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    SYNCHRONIZE = 0x00100000
    WAIT_TIMEOUT = 0x00000102
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    parent_handle = kernel32.OpenProcess(SYNCHRONIZE, False, parent_pid)

def cleanup():
    for extension in extensions:
        try:
            os.unlink(os.path.join(socket_dir, session_id + "." + extension))
        except FileNotFoundError:
            pass
        except OSError:
            pass

def parent_alive():
    if os.name == "nt":
        return bool(parent_handle) and kernel32.WaitForSingleObject(parent_handle, 0) == WAIT_TIMEOUT
    if os.getppid() != parent_pid:
        return False
    try:
        os.kill(parent_pid, 0)
    except OSError:
        return False
    return True

try:
    while parent_alive():
        time.sleep(0.25)
finally:
    if parent_handle:
        kernel32.CloseHandle(parent_handle)
    cleanup()
"#,
        )
        .arg(parent_pid)
        .arg(socket_dir)
        .arg(session_id)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|err| format!("failed to start dashboard watchdog: {err}"))
}
