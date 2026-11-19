include!(concat!(env!("OUT_DIR"), "/agent_browser_upstream.rs"));

mod confirmation;
mod documents;

mod engine;
mod namespace;
mod options;

pub use engine::{Engine, EngineIdentity, INTERNAL_SHUTDOWN_ACTION};
pub use namespace::Namespace;
pub use options::EngineOptions;

pub fn browser_cache_dir() -> std::path::PathBuf {
    install::get_browsers_dir()
}

pub fn find_chrome_executable() -> Option<std::path::PathBuf> {
    native::cdp::chrome::find_chrome()
}

pub fn run_browser_install(with_deps: bool) {
    install::run_install(with_deps);
}

/// The directory that holds socket and session files for `namespace`.
pub fn socket_dir(namespace: &Namespace) -> std::path::PathBuf {
    let _entered = namespace.enter();
    connection::get_socket_dir()
}
