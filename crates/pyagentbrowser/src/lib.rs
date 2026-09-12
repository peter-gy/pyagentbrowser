use pyo3::prelude::*;

mod browser;
mod cancellation;
mod dashboard;
mod maintenance;
mod session;
mod skill_data {
    include!(concat!(env!("OUT_DIR"), "/pyagentbrowser_skill_data.rs"));
}

use browser::PyNativeBrowser;
use cancellation::PyNativeCancellation;

#[pyfunction]
fn skill_data_json() -> &'static str {
    skill_data::SKILL_DATA_JSON
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
    m.add_function(wrap_pyfunction!(skill_data_json, m)?)?;
    m.add("__agent_browser_version__", agent_browser::VERSION)?;
    Ok(())
}
