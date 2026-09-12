use super::super::super::{
    patch::replace_once_named,
    source::{line, path_literal, read_rewrite_source, require_file},
};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub(crate) fn rewrite_cdp_module(out_dir: &Path, source: &Path) -> PathBuf {
    let root = source.parent().expect("CDP module directory");
    let client_source = root.join("client.rs");
    require_file(&client_source);
    let contents = read_rewrite_source(&client_source, "CDP client").feature("documents");
    let contents = replace_once_named(
        contents, "context index field", "    next_id: AtomicU64,",
        "    pub(crate) documents: Arc<crate::documents::ClientDocuments>,\n    next_id: AtomicU64,",
    );
    let contents = replace_once_named(
        contents, "context index construction", "        let pending_clone = pending.clone();",
        "        let documents = Arc::new(crate::documents::ClientDocuments::default());\n        let reader_documents = documents.clone();\n        let pending_clone = pending.clone();",
    );
    let contents = replace_once_named(
        contents, "context event indexing", "                    let routed = event.session_id.as_deref().is_some_and(|sid| {",
        "                    reader_documents.apply(&event);\n                    let routed = event.session_id.as_deref().is_some_and(|sid| {",
    );
    let contents = replace_once_named(
        contents,
        "context client initialization",
        "            next_id: AtomicU64::new(1),",
        "            documents,\n            next_id: AtomicU64::new(1),",
    );
    let client = out_dir.join("agent_browser_cdp_client.rs");
    fs::write(&client, contents).expect("write CDP client");
    let mut module = String::new();
    for name in [
        "chrome",
        "client",
        "discovery",
        "lightpanda",
        "types",
        "windows_process",
    ] {
        let path = if name == "client" {
            client.clone()
        } else {
            root.join(format!("{name}.rs"))
        };
        if name != "client" {
            require_file(&path);
        }
        if name == "windows_process" {
            module.push_str("#[cfg(windows)]\n");
        }
        line(
            &mut module,
            format_args!("#[path = \"{}\"] pub mod {name};", path_literal(&path)),
        );
    }
    let destination = out_dir.join("agent_browser_cdp.rs");
    fs::write(&destination, module).expect("write CDP module");
    destination
}
