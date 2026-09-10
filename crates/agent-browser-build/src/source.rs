use std::{
    fmt::{Arguments, Write as _},
    fs,
    ops::{Deref, Range},
    path::{Path, PathBuf},
};

use crate::report::{self, PatchReport};

struct Introduced {
    range: Range<usize>,
    patch: String,
}

pub(crate) struct Source {
    path: PathBuf,
    feature: String,
    text: String,
    introduced: Vec<Introduced>,
}

impl Source {
    pub(crate) fn new(path: &Path, text: String) -> Self {
        Self {
            path: path.to_owned(),
            feature: "embedding".into(),
            text,
            introduced: Vec::new(),
        }
    }

    pub(crate) fn feature(mut self, name: &str) -> Self {
        self.feature = name.into();
        self
    }

    pub(crate) fn replace(
        mut self,
        name: &str,
        expected: &str,
        replacement: &str,
        count: usize,
        allowed_dependencies: &[&str],
    ) -> Self {
        assert!(
            !expected.is_empty(),
            "{}: patch {name} requires a nonempty anchor",
            self.path.display()
        );
        let ranges: Vec<_> = self
            .text
            .match_indices(expected)
            .map(|(start, value)| start..start + value.len())
            .collect();
        assert_eq!(
            ranges.len(),
            count,
            "{}: {} patch {name} anchor count changed",
            self.path.display(),
            self.feature
        );
        let mut dependencies = Vec::new();
        for range in &ranges {
            for prior in &self.introduced {
                if range.start < prior.range.end
                    && prior.range.start < range.end
                    && !dependencies.contains(&prior.patch)
                {
                    assert!(allowed_dependencies.contains(&prior.patch.as_str()), "{}: patch {name} overlaps generated patch {}. Declare and audit that dependency", self.path.display(), prior.patch);
                    dependencies.push(prior.patch.clone());
                }
            }
        }
        for dependency in allowed_dependencies {
            assert!(
                dependencies.iter().any(|actual| actual == dependency),
                "{}: patch {name} declared dependency {dependency} was not used",
                self.path.display()
            );
        }
        for range in ranges.into_iter().rev() {
            let length = range.len();
            let mut retained = Vec::new();
            for prior in self.introduced.drain(..) {
                if prior.range.end <= range.start {
                    retained.push(prior);
                } else if prior.range.start >= range.end {
                    retained.push(Introduced {
                        range: prior.range.start - length + replacement.len()
                            ..prior.range.end - length + replacement.len(),
                        patch: prior.patch,
                    });
                } else {
                    if prior.range.start < range.start {
                        retained.push(Introduced {
                            range: prior.range.start..range.start,
                            patch: prior.patch.clone(),
                        });
                    }
                    if prior.range.end > range.end {
                        retained.push(Introduced {
                            range: range.start + replacement.len()
                                ..prior.range.end - length + replacement.len(),
                            patch: prior.patch,
                        });
                    }
                }
            }
            self.introduced = retained;
            self.text.replace_range(range.clone(), replacement);
            self.introduced.push(Introduced {
                range: range.start..range.start + replacement.len(),
                patch: name.into(),
            });
        }
        report::patch(PatchReport {
            module: self.path.clone(),
            feature: self.feature.clone(),
            name: name.into(),
            matches: count,
            dependencies,
        });
        self
    }
}

impl Deref for Source {
    type Target = str;
    fn deref(&self) -> &str {
        &self.text
    }
}

impl AsRef<[u8]> for Source {
    fn as_ref(&self) -> &[u8] {
        self.text.as_bytes()
    }
}

pub(crate) fn read_rewrite_source(source: &Path, module: &str) -> Source {
    require_file(source);
    Source::new(
        source,
        fs::read_to_string(source)
            .unwrap_or_else(|error| panic!("failed to read upstream {module}: {error}"))
            .replace("\r\n", "\n"),
    )
}

pub(crate) fn require_file(path: &Path) {
    assert!(
        path.is_file(),
        "required upstream agent-browser file is missing: {}",
        path.display()
    );
    report::input(path);
}

pub(crate) fn path_literal(path: &Path) -> String {
    path.to_string_lossy()
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
}

pub(crate) fn line(output: &mut String, args: Arguments<'_>) {
    writeln!(output, "{args}").expect("write generated module source");
}
