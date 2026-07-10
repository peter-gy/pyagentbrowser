include!(concat!(env!("OUT_DIR"), "/agent_browser_upstream.rs"));

/// Run the background maintenance performed by the upstream native daemon.
///
/// The Python extension embeds the native engine in-process, so it does not
/// execute `native::daemon`. Calling this on the same cadence keeps browser
/// exit detection, CDP event draining, and periodic restore autosaves aligned
/// with the daemon runtime.
pub async fn maintain_browser_state(
    state: &mut native::actions::DaemonState,
    autosave_interval_ms: u64,
) {
    let process_exited = state
        .browser
        .as_mut()
        .map(native::browser::BrowserManager::has_process_exited)
        .unwrap_or(false);

    if process_exited {
        let _ = native::actions::close_current_browser(state).await;
    } else if state.browser.is_some() {
        state.drain_cdp_events_background().await;
        native::actions::maybe_autosave_restore_state(state, autosave_interval_ms).await;
    }
}

pub fn browser_cache_dir() -> std::path::PathBuf {
    install::get_browsers_dir()
}

pub fn find_chrome_executable() -> Option<std::path::PathBuf> {
    native::cdp::chrome::find_chrome()
}

pub fn run_browser_install(with_deps: bool) {
    install::run_install(with_deps);
}

pub fn socket_dir() -> std::path::PathBuf {
    connection::get_socket_dir()
}

pub fn socket_dir_for_namespace(namespace: Option<&str>) -> std::path::PathBuf {
    connection::get_socket_dir_for_namespace(namespace)
}
