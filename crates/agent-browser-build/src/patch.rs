use crate::source::Source;

pub(crate) fn replace_once_named(
    contents: Source,
    name: &str,
    expected: &str,
    replacement: &str,
) -> Source {
    replace_n_named(contents, name, expected, replacement, 1)
}

pub(crate) fn replace_n_named(
    contents: Source,
    name: &str,
    expected: &str,
    replacement: &str,
    count: usize,
) -> Source {
    contents.replace(name, expected, replacement, count, &[])
}

pub(crate) fn replace_after_named(
    contents: Source,
    name: &str,
    expected: &str,
    replacement: &str,
    dependencies: &[&str],
) -> Source {
    contents.replace(name, expected, replacement, 1, dependencies)
}
