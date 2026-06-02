use std::{
    env, fs, io,
    path::{Path, PathBuf},
};

use serde_json::json;

const UPSTREAM_SKILL_DATA: &str = "third_party/agent-browser/skill-data";

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let workspace_dir = manifest_dir
        .parent()
        .and_then(Path::parent)
        .expect("pyagentbrowser crate must live under crates/pyagentbrowser");
    let skill_data_dir = workspace_dir.join(UPSTREAM_SKILL_DATA);

    assert!(
        skill_data_dir.is_dir(),
        "missing upstream skill-data at {}; initialize the submodule or build from an sdist that includes it",
        skill_data_dir.display()
    );

    println!("cargo:rerun-if-changed={}", skill_data_dir.display());

    let mut paths = Vec::new();
    collect_files(&skill_data_dir, &mut paths).unwrap();
    paths.sort();

    let mut files = Vec::new();
    for path in paths {
        println!("cargo:rerun-if-changed={}", path.display());
        let relative = path.strip_prefix(&skill_data_dir).unwrap();
        let relative = relative
            .components()
            .map(|component| component.as_os_str().to_string_lossy())
            .collect::<Vec<_>>()
            .join("/");
        let content = fs::read_to_string(&path).unwrap_or_else(|err| {
            panic!("failed to read skill-data file {}: {err}", path.display())
        });
        files.push(json!({
            "path": relative,
            "content": content,
        }));
    }

    let encoded = serde_json::to_string(&files).unwrap();
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    fs::write(
        out_dir.join("pyagentbrowser_skill_data.rs"),
        format!("pub const SKILL_DATA_JSON: &str = {encoded:?};\n"),
    )
    .unwrap();
}

fn collect_files(root: &Path, paths: &mut Vec<PathBuf>) -> io::Result<()> {
    for entry in fs::read_dir(root)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            collect_files(&path, paths)?;
        } else if path.is_file() {
            paths.push(path);
        }
    }
    Ok(())
}
