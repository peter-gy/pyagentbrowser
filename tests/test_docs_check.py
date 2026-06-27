from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_docs import DocsCheckError, check_docs, iter_text_files


def test_docs_checker_missing_root_is_error(tmp_path: Path) -> None:
    with pytest.raises(DocsCheckError, match="does not exist"):
        iter_text_files((tmp_path / "missing",))


def test_docs_checker_rejects_unsupported_navigation_api(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Use browser.open for navigation.\n", encoding="utf-8")

    with pytest.raises(DocsCheckError, match=r"forbidden browser\.open"):
        check_docs((readme,))


def test_docs_checker_rejects_distribution_name_as_import_package(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("from pyagentbrowser import Browser\n", encoding="utf-8")

    with pytest.raises(DocsCheckError, match="forbidden pyagentbrowser import"):
        check_docs((readme,))
