use super::super::{
    patch::replace_once_named,
    source::{read_rewrite_source, Source},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_frame_capture(contents: Source) -> Source {
    const UPSTREAM_OPTIONS_END: &str = r#"        output_dir: cmd
            .get("screenshotDir")
            .and_then(|v| v.as_str())
            .map(String::from),
    };

    if annotate {"#;
    const FRAME_OPTIONS_END: &str = r#"        output_dir: cmd
            .get("screenshotDir")
            .and_then(|v| v.as_str())
            .map(String::from),
        frame_id: state.active_frame_id.clone(),
    };

    if options.frame_id.is_some() && options.full_page {
        return Err("Frame screenshots capture the rendered frame rectangle. fullPage is a page capture option".to_string());
    }
    if options.frame_id.is_some() && annotate {
        return Err("Annotated frame screenshots require selector-scoped page capture".to_string());
    }

    if annotate {"#;
    const UPSTREAM_DIFF_OPTIONS: &str = r#"        annotate: false,
        output_dir: None,
    };

    let result = screenshot::take_screenshot("#;
    const FRAME_DIFF_OPTIONS: &str = r#"        annotate: false,
        output_dir: None,
        frame_id: state.active_frame_id.clone(),
    };

    let result = screenshot::take_screenshot("#;
    const UPSTREAM_SCREENSHOT_RESULT: &str =
        r#"    let mut response = json!({ "path": result.path });"#;
    const SCOPED_SCREENSHOT_RESULT: &str = r#"    let origin = eval_body_in_active_frame(
        mgr,
        state.active_frame_id.as_deref(),
        &session_id,
        &state.iframe_sessions,
        "(root) => root.defaultView.location.href",
    )
    .await?
    .as_str()
    .unwrap_or_default()
    .to_string();
    let target_id = mgr.active_target_id().ok();
    let mut response = json!({
        "path": result.path,
        "origin": origin,
        "targetId": target_id,
        "frameId": state.active_frame_id.clone(),
    });"#;
    let rewritten = replace_once_named(
        contents,
        "frame screenshot options",
        UPSTREAM_OPTIONS_END,
        FRAME_OPTIONS_END,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame diff screenshot options",
        UPSTREAM_DIFF_OPTIONS,
        FRAME_DIFF_OPTIONS,
    );
    replace_once_named(
        rewritten,
        "screenshot document identity",
        UPSTREAM_SCREENSHOT_RESULT,
        SCOPED_SCREENSHOT_RESULT,
    )
}

pub(crate) fn rewrite_screenshot_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_screenshot.rs");
    let contents = read_rewrite_source(source, "screenshot file").feature("capture");
    const UPSTREAM_OPTIONS: &str = r#"    pub annotate: bool,
    pub output_dir: Option<String>,
}"#;
    const FRAME_OPTIONS: &str = r#"    pub annotate: bool,
    pub output_dir: Option<String>,
    pub frame_id: Option<String>,
}"#;
    const UPSTREAM_DEFAULT: &str = r#"            annotate: false,
            output_dir: None,
        }"#;
    const FRAME_DEFAULT: &str = r#"            annotate: false,
            output_dir: None,
            frame_id: None,
        }"#;
    const UPSTREAM_CAPTURE_BRANCH: &str = r#"    if options.full_page {
        let metrics: Value = client"#;
    const FRAME_CAPTURE_BRANCH: &str = r#"    if let Some(frame_id) = options.frame_id.as_deref() {
        let rect = crate::documents::frame_rect(client, session_id, iframe_sessions, frame_id).await?;
        params.clip = Some(Viewport {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            scale: 1.0,
        });
    } else if options.full_page {
        let metrics: Value = client"#;

    let rewritten = replace_once_named(
        contents,
        "frame screenshot option",
        UPSTREAM_OPTIONS,
        FRAME_OPTIONS,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame screenshot default",
        UPSTREAM_DEFAULT,
        FRAME_DEFAULT,
    );
    let rewritten = replace_once_named(
        rewritten,
        "frame screenshot clip",
        UPSTREAM_CAPTURE_BRANCH,
        FRAME_CAPTURE_BRANCH,
    );
    fs::write(destination.as_path(), rewritten).expect("failed to write generated screenshot file");
    destination
}

pub(crate) fn rewrite_snapshot_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_snapshot.rs");
    let contents = read_rewrite_source(source, "snapshot file").feature("capture");
    const UPSTREAM_AX_SCOPE: &str = r#"    let (ax_params, effective_session_id) =
        resolve_ax_session(frame_id, session_id, iframe_sessions);"#;
    const NESTED_AX_SCOPE: &str = r#"    let parent_session_id = match frame_id {
        Some(frame) => crate::documents::session_for_frame(client, session_id, iframe_sessions, frame).await?,
        None => session_id,
    };
    let (ax_params, effective_session_id) =
        resolve_ax_session(frame_id, parent_session_id, iframe_sessions);"#;

    let rewritten = replace_once_named(
        contents,
        "nested frame accessibility session",
        UPSTREAM_AX_SCOPE,
        NESTED_AX_SCOPE,
    );
    fs::write(destination.as_path(), rewritten).expect("failed to write generated snapshot file");
    destination
}
