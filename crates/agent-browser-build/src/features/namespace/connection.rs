use super::super::super::{
    patch::replace_once_named,
    source::{read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_connection_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_connection.rs");
    let contents = read_rewrite_source(source, "connection file").feature("namespace");
    let contents = rewrite_connection_namespace(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated connection file");
    destination
}

pub(crate) fn rewrite_connection_namespace(contents: Source) -> Source {
    const UPSTREAM_SOCKET_DIR: &str = r#"pub fn get_socket_dir() -> PathBuf {
    // 1. Explicit override (ignore empty string)
    let base = if let Ok(dir) = env::var("AGENT_BROWSER_SOCKET_DIR") {
        if !dir.is_empty() {
            PathBuf::from(dir)
        } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
            if !runtime_dir.is_empty() {
                PathBuf::from(runtime_dir).join("agent-browser")
            } else if let Some(home) = dirs::home_dir() {
                home.join(".agent-browser")
            } else {
                env::temp_dir().join("agent-browser")
            }
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
        if !runtime_dir.is_empty() {
            PathBuf::from(runtime_dir).join("agent-browser")
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Some(home) = dirs::home_dir() {
        home.join(".agent-browser")
    } else {
        env::temp_dir().join("agent-browser")
    };

    if let Ok(namespace) = env::var("AGENT_BROWSER_NAMESPACE") {
        let namespace = sanitize_session_component(&namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("run");
        }
    }

    base
}"#;
    const REWRITTEN_SOCKET_DIR: &str = r#"pub fn get_socket_dir() -> PathBuf {
    let namespace = env::var("AGENT_BROWSER_NAMESPACE").ok();
    get_socket_dir_for_namespace(namespace.as_deref())
}

pub fn get_socket_dir_for_namespace(namespace: Option<&str>) -> PathBuf {
    // 1. Explicit override (ignore empty string)
    let base = if let Ok(dir) = env::var("AGENT_BROWSER_SOCKET_DIR") {
        if !dir.is_empty() {
            PathBuf::from(dir)
        } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
            if !runtime_dir.is_empty() {
                PathBuf::from(runtime_dir).join("agent-browser")
            } else if let Some(home) = dirs::home_dir() {
                home.join(".agent-browser")
            } else {
                env::temp_dir().join("agent-browser")
            }
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Ok(runtime_dir) = env::var("XDG_RUNTIME_DIR") {
        if !runtime_dir.is_empty() {
            PathBuf::from(runtime_dir).join("agent-browser")
        } else if let Some(home) = dirs::home_dir() {
            home.join(".agent-browser")
        } else {
            env::temp_dir().join("agent-browser")
        }
    } else if let Some(home) = dirs::home_dir() {
        home.join(".agent-browser")
    } else {
        env::temp_dir().join("agent-browser")
    };

    if let Some(namespace) = namespace {
        let namespace = sanitize_session_component(namespace);
        if !namespace.is_empty() {
            return base.join("namespaces").join(namespace).join("run");
        }
    }

    base
}"#;

    let rewritten = replace_once_named(
        contents,
        "connection namespace socket dir",
        UPSTREAM_SOCKET_DIR,
        REWRITTEN_SOCKET_DIR,
    );
    assert!(
        rewritten.contains("pub fn get_socket_dir_for_namespace("),
        "upstream socket directory helper changed"
    );
    rewritten
}
