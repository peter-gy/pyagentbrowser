use super::super::{
    patch::replace_once_named,
    source::{path_literal, read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_dashboard_streaming(contents: Source) -> Source {
    assert!(
        contents.contains("use super::stream::{self, IdleActivity, StreamServer};"),
        "upstream dashboard stream import moved"
    );
    assert!(
        contents.contains("pub fn new_with_stream("),
        "upstream DaemonState stream constructor moved"
    );
    assert!(
        contents.contains("server.broadcast_command(action, &id, cmd_for_broadcast);"),
        "upstream command stream broadcast moved"
    );
    assert!(
        contents.contains("\"stream_enable\" => handle_stream_enable(cmd, state).await,")
            && contents.contains("\"stream_disable\" => handle_stream_disable(state).await,")
            && contents.contains("\"stream_status\" => handle_stream_status(state).await,"),
        "upstream stream command dispatch moved"
    );
    contents
}

pub(crate) fn rewrite_stream_result_success(contents: Source) -> Source {
    const UPSTREAM_SUCCESS_CHECK: &str = r#"        let success = resp
            .get("status")
            .and_then(|v| v.as_str())
            .is_some_and(|s| s == "success");"#;
    const REWRITTEN_SUCCESS_CHECK: &str = r#"        let success = resp
            .get("success")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);"#;

    let rewritten = replace_once_named(
        contents,
        "stream result success field",
        UPSTREAM_SUCCESS_CHECK,
        REWRITTEN_SUCCESS_CHECK,
    );
    assert!(
        rewritten.contains(".get(\"success\")"),
        "upstream stream result success handling changed"
    );
    rewritten
}

pub(crate) fn rewrite_stream_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_stream.rs");
    let stream_dir = source.parent().expect("stream module must have a parent");
    let http_path = rewrite_stream_http_module(out_dir, &stream_dir.join("http.rs"));
    let mut contents = read_rewrite_source(source, "stream module").feature("dashboard");

    contents = replace_once_named(
        contents,
        "stream cdp_loop module",
        "mod cdp_loop;\n",
        &format!(
            "#[path = \"{}\"]\nmod cdp_loop;\n",
            path_literal(&stream_dir.join("cdp_loop.rs"))
        ),
    );
    contents = replace_once_named(
        contents,
        "stream chat module",
        "pub(crate) mod chat;\n",
        &format!(
            "#[path = \"{}\"]\npub(crate) mod chat;\n",
            path_literal(&stream_dir.join("chat.rs"))
        ),
    );
    contents = replace_once_named(contents, "stream dashboard module", "mod dashboard;\n", "");
    contents = replace_once_named(
        contents,
        "stream discovery module",
        "mod discovery;\n",
        &format!(
            "#[path = \"{}\"]\nmod discovery;\n",
            path_literal(&stream_dir.join("discovery.rs"))
        ),
    );
    contents = replace_once_named(
        contents,
        "stream http module",
        "mod http;\n",
        &format!("#[path = \"{}\"]\nmod http;\n", path_literal(&http_path)),
    );
    contents = replace_once_named(
        contents,
        "stream websocket module",
        "mod websocket;\n",
        &format!(
            "#[path = \"{}\"]\nmod websocket;\n",
            path_literal(&stream_dir.join("websocket.rs"))
        ),
    );
    contents = replace_once_named(
        contents,
        "stream dashboard export",
        "pub use dashboard::{\n    is_valid_dashboard_access_token, normalize_dashboard_allowed_origins, run_dashboard_server,\n};\n",
        "",
    );

    fs::write(destination.as_path(), contents).expect("failed to write generated stream module");
    destination
}

pub(crate) fn rewrite_stream_http_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_stream_http.rs");
    let contents = read_rewrite_source(source, "stream http module").feature("dashboard");
    let contents = replace_once_named(
        contents,
        "rust_embed import",
        "use rust_embed::Embed;\n",
        "",
    );
    let contents = replace_once_named(
        contents,
        "dashboard spawn_session import",
        "use super::dashboard::spawn_session;\n",
        "",
    );
    let contents = replace_once_named(
        contents,
        "dashboard assets embed",
        "#[derive(Embed)]\n#[folder = \"../packages/dashboard/out/\"]\nstruct DashboardAssets;\n\n",
        "",
    );
    let contents = replace_once_named(
        contents,
        "stream server session spawning",
        r##"        if path == "/api/sessions" {
            let result = spawn_session(body_str).await;
            let (status, resp_body) = match result {
                Ok(msg) => ("200 OK", msg),
                Err(e) => (
                    "400 Bad Request",
                    format!(
                        r#"{{"success":false,"error":{}}}"#,
                        serde_json::to_string(&e).unwrap_or_else(|_| format!("\"{}\"", e))
                    ),
                ),
            };
            let response = format!(
                "HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n{CORS_HEADERS}\r\n",
                resp_body.len()
            );
            let _ = stream.write_all(response.as_bytes()).await;
            let _ = stream.write_all(resp_body.as_bytes()).await;
            return;
        }
"##,
        r##"        if path == "/api/sessions" {
            let resp_body = r#"{"success":false,"error":"Session creation is not available from the pyagentbrowser SDK stream server"}"#;
            let response = format!(
                "HTTP/1.1 400 Bad Request\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n{CORS_HEADERS}\r\n",
                resp_body.len()
            );
            let _ = stream.write_all(response.as_bytes()).await;
            let _ = stream.write_all(resp_body.as_bytes()).await;
            return;
        }
"##,
    );
    let contents = replace_once_named(
        contents,
        "dashboard asset serving",
        r###"pub(super) fn serve_embedded_file(url_path: &str) -> (&'static str, &'static str, Vec<u8>) {
    let clean = url_path.trim_start_matches('/');
    let key = if clean.is_empty() {
        "index.html"
    } else {
        clean
    };

    let file = DashboardAssets::get(key).or_else(|| DashboardAssets::get("index.html"));

    match file {
        Some(content) => {
            let ext = key.rsplit('.').next().unwrap_or("");
            let ct = match ext {
                "html" => "text/html; charset=utf-8",
                "js" => "application/javascript; charset=utf-8",
                "css" => "text/css; charset=utf-8",
                "json" => "application/json; charset=utf-8",
                "svg" => "image/svg+xml",
                "png" => "image/png",
                "ico" => "image/x-icon",
                "woff2" => "font/woff2",
                "woff" => "font/woff",
                "txt" => "text/plain; charset=utf-8",
                _ => "application/octet-stream",
            };
            ("200 OK", ct, content.data.to_vec())
        }
        None => (
            "404 Not Found",
            "text/html; charset=utf-8",
            b"<html><body><p>404 Not Found</p></body></html>".to_vec(),
        ),
    }
}"###,
        r##"pub(super) fn serve_embedded_file(_url_path: &str) -> (&'static str, &'static str, Vec<u8>) {
    (
        "404 Not Found",
        "application/json; charset=utf-8",
        br#"{"success":false,"error":"Dashboard assets are not embedded in pyagentbrowser"}"#.to_vec(),
    )
}
"##,
    );
    fs::write(destination.as_path(), contents)
        .expect("failed to write generated stream http module");
    destination
}
