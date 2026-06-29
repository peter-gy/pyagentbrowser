include!(concat!(env!("OUT_DIR"), "/agent_browser_upstream.rs"));

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
