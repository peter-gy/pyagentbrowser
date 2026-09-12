mod features;
mod patch;
mod protocol;
mod registry;
mod report;
mod source;

#[cfg(test)]
#[path = "../tests/support/build_contracts.rs"]
mod build_contracts;

use serde::Serialize;
use std::path::Path;

pub use report::{PatchReport, Report};

#[derive(Serialize)]
/// Generation failure with the completed portion of the source audit.
pub struct BuildError {
    pub message: String,
    pub report: Report,
}

impl std::fmt::Display for BuildError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::fmt::Debug for BuildError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("BuildError")
            .field("message", &self.message)
            .finish()
    }
}

impl std::error::Error for BuildError {}

/// Write adapted Rust modules and protocol types into `output_dir`.
///
/// `source_root` contains the upstream `cli` directory. The report names build
/// inputs and applied patches. A failed source contract returns the partial
/// report with its diagnostic.
pub fn generate(source_root: &Path, output_dir: &Path) -> Result<Report, BuildError> {
    report::begin(source_root);
    let result = std::panic::catch_unwind(|| {
        std::fs::create_dir_all(output_dir).expect("create adapter output directory");
        registry::write_upstream_modules(source_root, output_dir);
        protocol::generate(&source_root.join("cli/cdp-protocol"), output_dir);
    });
    let report = report::finish();
    match result {
        Ok(()) => Ok(report),
        Err(payload) => Err(BuildError {
            message: payload
                .downcast_ref::<String>()
                .cloned()
                .or_else(|| {
                    payload
                        .downcast_ref::<&str>()
                        .map(|value| (*value).to_owned())
                })
                .unwrap_or_else(|| "adapter generation failed".to_owned()),
            report,
        }),
    }
}
