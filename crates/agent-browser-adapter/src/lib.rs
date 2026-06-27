include!(concat!(env!("OUT_DIR"), "/agent_browser_upstream.rs"));

pub fn socket_dir() -> std::path::PathBuf {
    connection::get_socket_dir()
}

pub fn socket_dir_for_namespace(namespace: Option<&str>) -> std::path::PathBuf {
    connection::get_socket_dir_for_namespace(namespace)
}
