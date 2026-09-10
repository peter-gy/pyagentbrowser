from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn


class PackageSmokeError(AssertionError):
    pass


ROOT = Path(__file__).resolve().parents[2]


def _fail(message: str) -> NoReturn:
    raise PackageSmokeError(message)


def _assert_present(names: set[str], required: Iterable[str], category: str) -> None:
    missing = sorted(set(required) - names)
    if missing:
        _fail(f"{category} missing required files: {missing}")


def _is_distribution_name_import_payload(name: str) -> bool:
    return name.startswith("pyagentbrowser/") or (
        name.startswith("pyagentbrowser.") and name.endswith((".py", ".pyi", ".so", ".pyd"))
    )
