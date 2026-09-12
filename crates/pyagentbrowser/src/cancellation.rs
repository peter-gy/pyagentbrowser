use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};

use pyo3::prelude::*;
use tokio::sync::Notify;

#[derive(Default)]
pub(crate) struct CancellationState {
    cancelled: AtomicBool,
    notify: Notify,
}

impl CancellationState {
    pub(crate) async fn cancelled(&self) {
        let notified = self.notify.notified();
        tokio::pin!(notified);
        notified.as_mut().enable();
        if !self.cancelled.load(Ordering::Acquire) {
            notified.await;
        }
    }
}

#[pyclass(name = "NativeCancellation", module = "agentbrowser._native", frozen)]
pub(crate) struct PyNativeCancellation {
    pub(crate) state: Arc<CancellationState>,
}

#[pymethods]
impl PyNativeCancellation {
    #[new]
    fn new() -> Self {
        Self {
            state: Arc::new(CancellationState::default()),
        }
    }

    fn cancel(&self) {
        self.state.cancelled.store(true, Ordering::Release);
        self.state.notify.notify_waiters();
    }
}
