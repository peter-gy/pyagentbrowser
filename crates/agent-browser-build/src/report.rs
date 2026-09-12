use std::{
    cell::RefCell,
    path::{Path, PathBuf},
};

use serde::Serialize;

#[derive(Default, Serialize)]
/// Source inputs and ordered transformations used to generate an adapter.
pub struct Report {
    pub source: PathBuf,
    pub inputs: Vec<PathBuf>,
    pub patches: Vec<PatchReport>,
}

#[derive(Serialize)]
/// One checked source replacement and the earlier patches it depends on.
pub struct PatchReport {
    pub module: PathBuf,
    pub feature: String,
    pub name: String,
    pub matches: usize,
    pub dependencies: Vec<String>,
}

thread_local! {
    static REPORT: RefCell<Report> = RefCell::new(Report::default());
}

pub(crate) fn begin(root: &Path) {
    REPORT.with(|report| {
        *report.borrow_mut() = Report {
            source: root.to_owned(),
            ..Report::default()
        }
    });
}

pub(crate) fn input(path: &Path) {
    REPORT.with(|report| {
        let mut report = report.borrow_mut();
        if !report.inputs.iter().any(|input| input == path) {
            report.inputs.push(path.to_owned());
        }
    });
}

pub(crate) fn patch(mut patch: PatchReport) {
    REPORT.with(|report| {
        let mut report = report.borrow_mut();
        if let Ok(relative) = patch.module.strip_prefix(&report.source) {
            patch.module = relative.to_owned();
        }
        report.patches.push(patch);
    });
}

pub(crate) fn finish() -> Report {
    REPORT.with(|report| std::mem::take(&mut *report.borrow_mut()))
}
