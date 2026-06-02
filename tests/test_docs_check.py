from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_docs import DocsCheckError, check_docs, iter_text_files


def test_docs_checker_missing_root_is_error(tmp_path: Path) -> None:
    with pytest.raises(DocsCheckError, match="does not exist"):
        iter_text_files((tmp_path / "missing",))


def test_docs_checker_rejects_stale_public_api_claim(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Use browser.open for navigation.\n", encoding="utf-8")

    with pytest.raises(DocsCheckError, match=r"forbidden browser\.open"):
        check_docs((readme,))
