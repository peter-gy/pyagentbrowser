fn main() {
    let manifest = std::path::PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("Cargo manifest directory"),
    );
    let output =
        std::path::PathBuf::from(std::env::var_os("OUT_DIR").expect("Cargo output directory"));
    let report =
        agent_browser_build::generate(&manifest.join("../../third_party/agent-browser"), &output)
            .unwrap_or_else(|error| panic!("{error}"));
    for input in report.inputs {
        println!("cargo:rerun-if-changed={}", input.display());
    }
}
