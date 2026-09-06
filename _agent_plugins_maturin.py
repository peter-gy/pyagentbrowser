"""PEP 517 backend that adds Agent Plugin resources to Maturin artifacts."""

from __future__ import annotations

import copy
import gzip
import os
import tarfile
import tempfile
from pathlib import Path

from agent_plugins.build import BuildBackend
from maturin import (
    prepare_metadata_for_build_editable,
    prepare_metadata_for_build_wheel,
)

_backend = BuildBackend("maturin")

build_editable = _backend.build_editable
build_wheel = _backend.build_wheel
get_requires_for_build_editable = _backend.get_requires_for_build_editable
get_requires_for_build_sdist = _backend.get_requires_for_build_sdist
get_requires_for_build_wheel = _backend.get_requires_for_build_wheel


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, object] | None = None,
) -> str:
    """Build an sdist and clamp every member to `SOURCE_DATE_EPOCH`."""
    filename = _backend.build_sdist(sdist_directory, config_settings)
    _normalize_sdist(Path(sdist_directory) / filename)
    return filename


def _normalize_sdist(sdist: Path) -> None:
    epoch = _source_date_epoch()
    if epoch is None:
        return

    with tempfile.NamedTemporaryFile(
        dir=sdist.parent,
        prefix=f".{sdist.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with (
            tarfile.open(sdist, "r:gz") as source,
            temporary_path.open("wb") as raw_target,
            gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_target,
                mtime=epoch,
            ) as compressed,
            tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as target,
        ):
            for member in source.getmembers():
                normalized = copy.copy(member)
                normalized.mtime = epoch
                normalized.pax_headers = {
                    key: value
                    for key, value in member.pax_headers.items()
                    if key not in {"atime", "ctime", "mtime"}
                }
                file_object = source.extractfile(member) if member.isfile() else None
                try:
                    target.addfile(normalized, file_object)
                finally:
                    if file_object is not None:
                        file_object.close()
        temporary_path.chmod(sdist.stat().st_mode & 0o777)
        temporary_path.replace(sdist)
    finally:
        temporary_path.unlink(missing_ok=True)


def _source_date_epoch() -> int | None:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    if value is None:
        return None
    try:
        epoch = int(value)
    except ValueError as error:
        raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer") from error
    if epoch < 0:
        raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer")
    return epoch


__all__ = [
    "build_editable",
    "build_sdist",
    "build_wheel",
    "get_requires_for_build_editable",
    "get_requires_for_build_sdist",
    "get_requires_for_build_wheel",
    "prepare_metadata_for_build_editable",
    "prepare_metadata_for_build_wheel",
]
