use super::{ControlStream, cleanup_dashboard_sidecar_files, handle_control_stream};
use serde_json::{Value, json};
use std::{
    io::{Cursor, Read, Result as IoResult, Write},
    path::{Path, PathBuf},
};

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
    let dir = std::env::temp_dir().join(format!("pyagentbrowser-{name}-{}", std::process::id()));
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
