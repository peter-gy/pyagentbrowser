from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.decode import optional_bool, optional_float, require_keys
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.storage.models import Cookie


def cookies_from_data(data: Mapping[str, Any]) -> tuple[Cookie, ...]:
    raw_cookies = data.get("cookies")
    if not isinstance(raw_cookies, list):
        raise NativeParseError("Cookie collection field 'cookies' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_cookies):
        raise NativeParseError("Cookie collection entries must be objects")
    return tuple(_cookie(cast(Mapping[str, Any], item)) for item in raw_cookies)


def _cookie(raw: Mapping[str, Any]) -> Cookie:
    http_only = raw.get("httpOnly") if "httpOnly" in raw else raw.get("http_only")
    require_keys(raw, "Cookie", "name", "value")
    return Cookie(
        name=str(raw.get("name", "")),
        value=str(raw.get("value", "")),
        domain=str(raw["domain"]) if raw.get("domain") is not None else None,
        path=str(raw["path"]) if raw.get("path") is not None else None,
        expires=optional_float(raw.get("expires")),
        http_only=optional_bool(http_only),
        secure=optional_bool(raw.get("secure")),
        same_site=str(raw["sameSite"]) if raw.get("sameSite") is not None else None,
        raw=raw,
    )
