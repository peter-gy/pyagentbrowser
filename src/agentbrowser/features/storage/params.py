from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agentbrowser.contracts.protocol import OMIT, optional, path_value
from agentbrowser.features.storage.models import SameSite, StorageArea


def cookies_get_params(
    urls: Sequence[str] | None = None,
    *,
    unsafe_export_all: bool = False,
) -> dict[str, Any]:
    return {
        "urls": list(urls) if urls is not None else OMIT,
        "unsafeExportAll": unsafe_export_all,
    }


def cookies_clear_params(*, unsafe_clear_all: bool = False) -> dict[str, Any]:
    return {"unsafeClearAll": unsafe_clear_all}


def cookies_set_params(
    name: str | None = None,
    value: str | None = None,
    *,
    cookies: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    url: str | None = None,
    domain: str | None = None,
    path: str | None = None,
    expires: int | None = None,
    http_only: bool | None = None,
    secure: bool | None = None,
    same_site: SameSite | None = None,
) -> dict[str, Any]:
    if cookies is not None:
        payload = (
            [dict(cookies)] if isinstance(cookies, Mapping) else [dict(item) for item in cookies]
        )
        return {"cookies": payload}

    if name is None or value is None:
        raise ValueError("cookies.set requires either cookies=... or name and value")

    return {
        "name": name,
        "value": value,
        "url": optional(url),
        "domain": optional(domain),
        "path": optional(path),
        "expires": optional(expires),
        "httpOnly": optional(http_only),
        "secure": optional(secure),
        "sameSite": optional(same_site),
    }


def storage_get_params(key: str | None = None, *, area: StorageArea = "local") -> dict[str, Any]:
    return {"type": area, "key": optional(key)}


def storage_set_params(key: str, value: str, *, area: StorageArea = "local") -> dict[str, Any]:
    return {"type": area, "key": key, "value": value}


def storage_clear_params(*, area: StorageArea = "local") -> dict[str, Any]:
    return {"type": area}


def state_path_params(path: str | Path | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "path": optional(path_value(path)),
        **{key: optional(value) for key, value in extra.items()},
    }
