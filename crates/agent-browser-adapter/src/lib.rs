include!(concat!(env!("OUT_DIR"), "/agent_browser_upstream.rs"));

pub fn socket_dir() -> std::path::PathBuf {
    connection::get_socket_dir()
}
