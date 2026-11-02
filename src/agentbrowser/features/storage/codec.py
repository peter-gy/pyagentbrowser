from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast, get_args

from agentbrowser.contracts.decode import (
    optional_string,
    required_bool,
    required_string,
    string_tuple,
)
from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.storage.models import Cookie, SameSite, StateLoadResult

_SAME_SITE = frozenset(get_args(SameSite))


def cookies_from_data(data: Mapping[str, Any]) -> tuple[Cookie, ...]:
    raw_cookies = data.get("cookies")
    if not isinstance(raw_cookies, list):
        raise NativeParseError("Cookie collection field 'cookies' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_cookies):
        raise NativeParseError("Cookie collection entries must be objects")
    return tuple(_cookie(cast(Mapping[str, Any], item)) for item in raw_cookies)


def _cookie(raw: Mapping[str, Any]) -> Cookie:
    action = "cookies_get"
    if "session" in raw:
        # Chrome DevTools `Network.Cookie`.
        expires = _number(raw.get("expires"), "expires", action=action)
        session = required_bool(raw, "session", action=action)
    else:
        # W3C WebDriver cookie from the Safari and iOS providers.
        expiry = raw.get("expiry")
        expires = -1.0 if expiry is None else _number(expiry, "expiry", action=action)
        session = expiry is None
    same_site = optional_string(raw, "sameSite", action=action)
    if same_site is not None and same_site not in _SAME_SITE:
        raise NativeParseError(f"{action} field 'sameSite' has unknown value '{same_site}'")
    return Cookie(
        name=required_string(raw, "name", action=action),
        value=required_string(raw, "value", action=action),
        domain=required_string(raw, "domain", action=action),
        path=required_string(raw, "path", action=action),
        expires=expires,
        http_only=required_bool(raw, "httpOnly", action=action),
        secure=required_bool(raw, "secure", action=action),
        session=session,
        same_site=cast(SameSite | None, same_site),
        raw=raw,
    )


def _number(value: Any, field: str, *, action: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise NativeParseError(f"{action} field '{field}' must be a number")
    return float(value)


def state_load_result_from_data(data: Mapping[str, Any]) -> StateLoadResult:
    action = "state_load"
    return StateLoadResult(
        path=Path(required_string(data, "path", action=action)),
        skipped_origins=string_tuple(data, "skippedOrigins", action=action),
    )
