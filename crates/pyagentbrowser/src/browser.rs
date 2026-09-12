use std::sync::Arc;

use agent_browser::{Engine, EngineOptions};
use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
};
use serde::Deserialize;
use serde_json::Value;

use crate::{
    cancellation::PyNativeCancellation,
    dashboard::{DashboardOption, validate_dashboard_session_id},
    maintenance::autosave_interval_ms,
    session::Session,
};

#[derive(Default, Deserialize)]
struct NativeBrowserOptions {
    #[serde(flatten)]
    engine: EngineOptions,
    autosave_interval_ms: Option<u64>,
    dashboard: Option<DashboardOption>,
}

#[pyclass(name = "NativeBrowser", module = "agentbrowser._native")]
pub(crate) struct PyNativeBrowser {
    session: Session,
}

#[pymethods]
impl PyNativeBrowser {
    #[new]
    #[pyo3(signature = (options_json=None))]
    fn new(py: Python<'_>, options_json: Option<&str>) -> PyResult<Self> {
        let options = match options_json {
            Some(raw) => serde_json::from_str::<NativeBrowserOptions>(raw).map_err(|error| {
                PyValueError::new_err(format!("invalid native options JSON: {error}"))
            })?,
            None => NativeBrowserOptions::default(),
        };
        let engine = Engine::new(&options.engine).map_err(PyValueError::new_err)?;
        let dashboard = match options.dashboard.and_then(DashboardOption::into_config) {
            Some(config) => {
                validate_dashboard_session_id(engine.identity().session)
                    .map_err(PyValueError::new_err)?;
                let executable = py
                    .import("sys")?
                    .getattr("executable")?
                    .extract::<String>()?;
                Some((config, executable))
            }
            None => None,
        };
        let session = Session::new(
            engine,
            autosave_interval_ms(options.autosave_interval_ms),
            dashboard,
        )
        .map_err(PyRuntimeError::new_err)?;
        Ok(Self { session })
    }

    #[pyo3(signature = (command_json, cancellation=None))]
    fn execute_json(
        &self,
        py: Python<'_>,
        command_json: &str,
        cancellation: Option<PyRef<'_, PyNativeCancellation>>,
    ) -> PyResult<String> {
        let command: Value = serde_json::from_str(command_json)
            .map_err(|error| PyValueError::new_err(format!("invalid command JSON: {error}")))?;
        if !command.is_object() {
            return Err(PyValueError::new_err("command JSON must be an object"));
        }
        let cancellation = cancellation.map(|token| Arc::clone(&token.state));
        let response = py
            .detach(|| self.session.execute(&command, cancellation))
            .map_err(PyRuntimeError::new_err)?;
        serde_json::to_string(&response).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize response: {error}"))
        })
    }
}
