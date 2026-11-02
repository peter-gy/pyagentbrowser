use pyo3::{prelude::*, types::PyTuple};

mod browser;
mod cancellation;
mod dashboard;
mod maintenance;
mod session;
mod skill_data {
    pub(crate) struct SkillRow {
        pub(crate) name: &'static str,
        pub(crate) description: &'static str,
        pub(crate) hidden: bool,
        pub(crate) files: std::ops::Range<usize>,
    }

    // Build-time tables: `SKILLS` sorted by name, with each row's `files`
    // range indexing the parallel `FILE_PATHS` and `FILE_CONTENTS` columns.
    include!(concat!(env!("OUT_DIR"), "/pyagentbrowser_skill_data.rs"));

    pub(crate) fn find(name: &str) -> Option<&'static SkillRow> {
        let index = SKILLS.binary_search_by(|row| row.name.cmp(name)).ok()?;
        Some(&SKILLS[index])
    }

    pub(crate) fn paths(row: &SkillRow) -> &'static [&'static str] {
        &FILE_PATHS[row.files.clone()]
    }

    pub(crate) fn file(row: &SkillRow, path: &str) -> Option<&'static str> {
        let index = paths(row).binary_search(&path).ok()?;
        Some(FILE_CONTENTS[row.files.start + index])
    }
}

use browser::PyNativeBrowser;
use cancellation::PyNativeCancellation;

#[pyfunction]
#[pyo3(signature = (include_hidden=false))]
fn skill_names(py: Python<'_>, include_hidden: bool) -> PyResult<Bound<'_, PyTuple>> {
    let names: Vec<_> = skill_data::SKILLS
        .iter()
        .filter(|row| include_hidden || !row.hidden)
        .map(|row| row.name)
        .collect();
    PyTuple::new(py, names)
}

#[pyfunction]
fn skill_record<'py>(
    py: Python<'py>,
    name: &str,
) -> PyResult<Option<(&'static str, bool, Bound<'py, PyTuple>)>> {
    skill_data::find(name)
        .map(|row| {
            Ok((
                row.description,
                row.hidden,
                PyTuple::new(py, skill_data::paths(row))?,
            ))
        })
        .transpose()
}

#[pyfunction]
fn skill_file(name: &str, path: &str) -> Option<&'static str> {
    skill_data::find(name).and_then(|row| skill_data::file(row, path))
}

#[pyfunction]
fn browser_cache_dir() -> String {
    agent_browser::browser_cache_dir()
        .to_string_lossy()
        .into_owned()
}

#[pyfunction]
fn find_chrome_executable() -> Option<String> {
    agent_browser::find_chrome_executable().map(|path| path.to_string_lossy().into_owned())
}

#[pyfunction]
#[pyo3(signature = (with_deps=false))]
fn _run_browser_install(with_deps: bool) {
    agent_browser::run_browser_install(with_deps);
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyNativeBrowser>()?;
    m.add_class::<PyNativeCancellation>()?;
    m.add_function(wrap_pyfunction!(browser_cache_dir, m)?)?;
    m.add_function(wrap_pyfunction!(find_chrome_executable, m)?)?;
    m.add_function(wrap_pyfunction!(_run_browser_install, m)?)?;
    m.add_function(wrap_pyfunction!(skill_names, m)?)?;
    m.add_function(wrap_pyfunction!(skill_record, m)?)?;
    m.add_function(wrap_pyfunction!(skill_file, m)?)?;
    m.add("__agent_browser_version__", agent_browser::VERSION)?;
    Ok(())
}
