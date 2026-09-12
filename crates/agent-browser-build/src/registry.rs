use super::features::{
    capture::*,
    confirmation::*,
    dashboard::*,
    documents::{client::*, elements::*, frames::*, scope::*, waits::*},
    embedding::*,
    namespace::{actions::*, connection::*, state::*, tabs::*},
};
use super::source::{line, path_literal, read_rewrite_source, require_file};
use std::{
    fs,
    path::{Path, PathBuf},
};

const ROOT_MODULES: &[(&str, &str)] = &[
    ("ca_bundle", "ca_bundle.rs"),
    ("color", "color.rs"),
    ("commands", "commands.rs"),
    ("connection", "connection.rs"),
    ("flags", "flags.rs"),
    ("install", "install.rs"),
    ("plugins", "plugins.rs"),
    ("read", "read.rs"),
    ("validation", "validation.rs"),
];

const NATIVE_MODULES: &[(&str, &str)] = &[
    ("a11y", "a11y/mod.rs"),
    ("actions", "actions.rs"),
    ("auth", "auth.rs"),
    ("browser", "browser.rs"),
    ("cdp", "cdp/mod.rs"),
    ("cookies", "cookies.rs"),
    ("diff", "diff.rs"),
    ("element", "element.rs"),
    ("inspect_server", "inspect_server.rs"),
    ("interaction", "interaction.rs"),
    ("network", "network.rs"),
    ("policy", "policy.rs"),
    ("providers", "providers.rs"),
    ("react", "react/mod.rs"),
    ("recording", "recording.rs"),
    ("screenshot", "screenshot.rs"),
    ("snapshot", "snapshot.rs"),
    ("state", "state.rs"),
    ("storage", "storage.rs"),
    ("stream", "stream/mod.rs"),
    ("tab_binding", "tab_binding.rs"),
    ("tracing", "tracing.rs"),
    ("webdriver", "webdriver/mod.rs"),
    ("webmcp", "webmcp.rs"),
];

pub(crate) fn write_upstream_modules(source_root: &Path, out_dir: &Path) {
    let native_module = write_native_module(source_root, out_dir);
    let upstream_root = source_root.join("cli/src");
    let root_module = out_dir.join("agent_browser_upstream.rs");
    let mut output = String::new();

    for (name, relative_path) in ROOT_MODULES {
        let path = upstream_root.join(relative_path);
        require_file(&path);
        let module_path = match *name {
            "connection" => rewrite_connection_module(out_dir, &path),
            _ => path,
        };
        line(
            &mut output,
            format_args!(
                "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
            ),
        );
        line(
            &mut output,
            format_args!("#[path = \"{}\"]", path_literal(&module_path)),
        );
        line(&mut output, format_args!("pub(crate) mod {name};"));
    }

    let test_utils = upstream_root.join("test_utils.rs");
    require_file(&test_utils);
    line(&mut output, format_args!("#[cfg(test)]"));
    line(
        &mut output,
        format_args!(
            "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
        ),
    );
    line(
        &mut output,
        format_args!("#[path = \"{}\"]", path_literal(&test_utils)),
    );
    line(&mut output, format_args!("pub(crate) mod test_utils;"));

    line(
        &mut output,
        format_args!(
            "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
        ),
    );
    line(
        &mut output,
        format_args!("#[path = \"{}\"]", path_literal(&native_module)),
    );
    line(&mut output, format_args!("pub(crate) mod native;"));
    line(
        &mut output,
        format_args!("pub const VERSION: &str = env!(\"CARGO_PKG_VERSION\");"),
    );

    fs::write(&root_module, output).expect("failed to write generated upstream module");
}

fn write_native_module(source_root: &Path, out_dir: &Path) -> PathBuf {
    let upstream_native = source_root.join("cli/src/native");
    let native_module = out_dir.join("agent_browser_native.rs");
    let mut output = String::new();

    for (name, relative_path) in NATIVE_MODULES {
        let path = upstream_native.join(relative_path);
        require_file(&path);
        let module_path = match *name {
            "actions" => rewrite_actions_module(out_dir, &path),
            "browser" => rewrite_browser_module(out_dir, &path),
            "cdp" => rewrite_cdp_module(out_dir, &path),
            "element" => rewrite_element_module(out_dir, &path),
            "screenshot" => rewrite_screenshot_module(out_dir, &path),
            "snapshot" => rewrite_snapshot_module(out_dir, &path),
            "state" => rewrite_state_module(out_dir, &path),
            "stream" => rewrite_stream_module(out_dir, &path),
            "tab_binding" => rewrite_tab_binding_module(out_dir, &path),
            _ => path,
        };
        line(
            &mut output,
            format_args!(
                "#[allow(dead_code, clippy::new_without_default, clippy::should_implement_trait)]"
            ),
        );
        if matches!(*name, "actions" | "stream") {
            line(&mut output, format_args!("#[allow(private_interfaces)]"));
        }
        if *name == "snapshot" {
            line(
                &mut output,
                format_args!("#[allow(unknown_lints, clippy::useless_borrows_in_formatting)]"),
            );
        }
        line(
            &mut output,
            format_args!("#[path = \"{}\"]", path_literal(&module_path)),
        );
        line(&mut output, format_args!("pub mod {name};"));
    }

    fs::write(&native_module, output).expect("failed to write generated native module");
    native_module
}

fn rewrite_actions_module(out_dir: &Path, source: &Path) -> PathBuf {
    let destination = out_dir.join("agent_browser_actions.rs");
    let contents = read_rewrite_source(source, "actions file");
    let contents = rewrite_confirmation_handling(contents.feature("confirmation"));
    let contents = rewrite_actions_namespace(contents.feature("namespace"));
    let contents = rewrite_scoped_page_commands(contents.feature("documents"));
    let contents = rewrite_frame_commands(contents);
    let contents = rewrite_scoped_waits(contents);
    let contents = rewrite_frame_capture(contents.feature("capture"));
    let contents = rewrite_dashboard_streaming(contents.feature("dashboard"));
    let contents = rewrite_stream_result_success(contents);
    fs::write(destination.as_path(), contents).expect("failed to write generated actions file");
    destination
}
