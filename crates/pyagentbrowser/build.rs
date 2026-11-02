use std::{
    collections::BTreeMap,
    env,
    fmt::Write as _,
    fs, io,
    path::{Path, PathBuf},
};

const UPSTREAM_SKILL_DATA: &str = "third_party/agent-browser/skill-data";
const MAIN_FILE: &str = "SKILL.md";

struct Skill {
    name: String,
    description: String,
    hidden: bool,
    files: BTreeMap<String, String>,
}

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

    let skills = load_skills(&skill_data_dir);
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    fs::write(
        out_dir.join("pyagentbrowser_skill_data.rs"),
        render_tables(&skills),
    )
    .unwrap();
}

/// Group every file under `<skill>/` by skill directory. A directory is a
/// skill when it contains `SKILL.md`, and its frontmatter name must match.
fn load_skills(root: &Path) -> Vec<Skill> {
    let mut paths = Vec::new();
    collect_files(root, &mut paths).unwrap();

    let mut grouped: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    for path in paths {
        println!("cargo:rerun-if-changed={}", path.display());
        let relative = path
            .strip_prefix(root)
            .unwrap()
            .components()
            .map(|component| component.as_os_str().to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        let [skill, part @ ..] = relative.as_slice() else {
            continue;
        };
        if part.is_empty() {
            continue;
        }
        let content = fs::read_to_string(&path).unwrap_or_else(|err| {
            panic!("failed to read skill-data file {}: {err}", path.display())
        });
        grouped.entry(skill.clone()).or_default().insert(
            part.join("/"),
            content.replace("\r\n", "\n").replace('\r', "\n"),
        );
    }

    grouped
        .into_iter()
        .filter_map(|(directory, files)| {
            let main = files.get(MAIN_FILE)?;
            let fields = frontmatter(main);
            let name = fields.get("name").unwrap_or_else(|| {
                panic!("{directory}/{MAIN_FILE} is missing frontmatter field 'name'")
            });
            assert_eq!(
                name, &directory,
                "{directory}/{MAIN_FILE} frontmatter name must match its directory"
            );
            Some(Skill {
                name: directory,
                description: fields.get("description").cloned().unwrap_or_default(),
                hidden: fields.get("hidden").is_some_and(|value| {
                    matches!(value.to_ascii_lowercase().as_str(), "true" | "yes")
                }),
                files,
            })
        })
        .collect()
}

/// Emit sorted skill rows plus parallel path and content columns. Each row
/// owns a contiguous `files` range, so lookups are two binary searches.
fn render_tables(skills: &[Skill]) -> String {
    let mut rows = String::new();
    let mut paths = String::new();
    let mut contents = String::new();
    let mut start = 0;
    for skill in skills {
        let end = start + skill.files.len();
        writeln!(
            rows,
            "    SkillRow {{ name: {:?}, description: {:?}, hidden: {}, files: {start}..{end} }},",
            skill.name, skill.description, skill.hidden
        )
        .unwrap();
        for (path, content) in &skill.files {
            writeln!(paths, "    {path:?},").unwrap();
            writeln!(contents, "    {content:?},").unwrap();
        }
        start = end;
    }
    format!(
        "pub static SKILLS: [SkillRow; {}] = [\n{rows}];\n\n\
         pub static FILE_PATHS: [&str; {start}] = [\n{paths}];\n\n\
         pub static FILE_CONTENTS: [&str; {start}] = [\n{contents}];\n",
        skills.len()
    )
}

/// Parse the flat `key: value` frontmatter used by skill files. Indented lines
/// continue the previous value, and matching outer quotes are removed.
fn frontmatter(content: &str) -> BTreeMap<String, String> {
    let mut fields = BTreeMap::new();
    let Some(after_opening) = content.trim_start().strip_prefix("---") else {
        return fields;
    };
    let Some(end) = after_opening.find("\n---") else {
        return fields;
    };
    let mut lines = after_opening[..end].lines().peekable();
    while let Some(line) = lines.next() {
        let Some((key, value)) = line.split_once(':') else {
            continue;
        };
        let mut value = unquote(value.trim()).to_owned();
        while let Some(next) =
            lines.next_if(|next| next.starts_with("  ") || next.starts_with('\t'))
        {
            let next = unquote(next.trim());
            if !next.is_empty() && !value.is_empty() {
                value.push(' ');
            }
            value.push_str(next);
        }
        fields.insert(key.trim().to_owned(), value);
    }
    fields
}

fn unquote(value: &str) -> &str {
    let bytes = value.as_bytes();
    if bytes.len() >= 2 && bytes[0] == bytes[bytes.len() - 1] && matches!(bytes[0], b'\'' | b'"') {
        &value[1..value.len() - 1]
    } else {
        value
    }
}

fn collect_files(root: &Path, paths: &mut Vec<PathBuf>) -> io::Result<()> {
    for entry in fs::read_dir(root)? {
        let path = entry?.path();
        if path.is_dir() {
            collect_files(&path, paths)?;
        } else if path.is_file() {
            paths.push(path);
        }
    }
    Ok(())
}
