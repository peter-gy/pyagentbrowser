use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};

use super::contexts::{Contexts, DocumentContext};
use crate::native::cdp::types::CdpEvent;

#[derive(Default)]
pub(crate) struct ClientDocuments {
    contexts: Mutex<Contexts>,
    frame: Mutex<Option<String>>,
    strict_refs: AtomicBool,
}

impl ClientDocuments {
    pub(crate) fn context(&self, session: &str, frame: &str) -> Option<DocumentContext> {
        self.contexts
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .document(session, frame)
    }

    pub(crate) fn apply(&self, event: &CdpEvent) {
        self.contexts
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .apply(event);
    }

    pub(crate) fn set_frame(&self, frame: Option<&str>) {
        *self.frame.lock().unwrap_or_else(|error| error.into_inner()) = frame.map(str::to_owned);
    }

    pub(crate) fn frame(&self) -> Option<String> {
        self.frame
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .clone()
    }

    pub(crate) fn set_strict_refs(&self, strict: bool) {
        self.strict_refs.store(strict, Ordering::Relaxed);
    }

    pub(crate) fn strict_refs(&self) -> bool {
        self.strict_refs.load(Ordering::Relaxed)
    }
}
