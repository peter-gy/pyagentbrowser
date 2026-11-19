//! The namespace an engine keeps its state and session files under.
//!
//! Upstream reads one namespace per process from `AGENT_BROWSER_NAMESPACE`. An
//! embedding process can own several engines, so the adapter rewrites those
//! reads to ask [`current`], which answers for the engine the calling thread
//! is working for. An engine enters its namespace around every poll of its own
//! futures. Tasks that upstream spawns run on the engine's runtime threads,
//! which enter it once through [`Namespace::enter_thread`].

use std::{
    cell::RefCell,
    env,
    future::Future,
    pin::Pin,
    task::{Context, Poll},
};

thread_local! {
    /// `None` until a thread enters a namespace. The inner `None` is an engine
    /// that keeps its files in the base directories.
    static ENTERED: RefCell<Option<Option<String>>> = const { RefCell::new(None) };
}

/// The namespace of the engine this thread works for. A thread that entered
/// none uses the process environment, as upstream does.
pub(crate) fn current() -> Option<String> {
    ENTERED
        .with_borrow(Clone::clone)
        .unwrap_or_else(|| env::var("AGENT_BROWSER_NAMESPACE").ok())
}

/// One engine's namespace. `None` keeps files in the base directories.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Namespace(Option<String>);

impl Namespace {
    pub fn new(name: Option<String>) -> Self {
        Self(name)
    }

    pub fn name(&self) -> Option<&str> {
        self.0.as_deref()
    }

    /// Enters the namespace until the guard drops, then restores what the
    /// thread had entered before.
    pub fn enter(&self) -> Entered {
        Entered(ENTERED.replace(Some(self.0.clone())))
    }

    /// Enters the namespace for the rest of the thread's life. Call it when a
    /// runtime thread that serves one engine starts.
    pub fn enter_thread(&self) {
        ENTERED.set(Some(self.0.clone()));
    }

    /// Runs `future` with the namespace entered on every poll, so the future
    /// can move between threads.
    pub(crate) fn scope<'a, T: 'a>(
        &self,
        future: impl Future<Output = T> + Send + 'a,
    ) -> impl Future<Output = T> + Send + 'a {
        Scoped {
            namespace: self.clone(),
            future: Box::pin(future),
        }
    }
}

/// Restores the thread's previous namespace on drop.
pub struct Entered(Option<Option<String>>);

impl Drop for Entered {
    fn drop(&mut self) {
        ENTERED.set(self.0.take());
    }
}

struct Scoped<'a, T> {
    namespace: Namespace,
    future: Pin<Box<dyn Future<Output = T> + Send + 'a>>,
}

impl<T> Future for Scoped<'_, T> {
    type Output = T;

    fn poll(mut self: Pin<&mut Self>, context: &mut Context<'_>) -> Poll<T> {
        let _entered = self.namespace.enter();
        self.future.as_mut().poll(context)
    }
}
