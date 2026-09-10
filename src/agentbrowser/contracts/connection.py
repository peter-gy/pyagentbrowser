from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentbrowser.contracts.types import JSONObject


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Browser proxy configuration."""

    server: str
    bypass: str | None = None
    username: str | None = None
    password: str | None = None

    def as_command_value(self) -> JSONObject:
        return {
            key: value
            for key, value in {
                "server": self.server,
                "bypass": self.bypass,
                "username": self.username,
                "password": self.password,
            }.items()
            if value is not None
        }


def proxy_value(
    value: str | ProxyConfig | Mapping[str, Any] | None,
) -> str | JSONObject | None:
    if isinstance(value, ProxyConfig):
        return value.as_command_value()
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items() if item is not None}
    return value


def normalize_url(url: str) -> str:
    lowered = url.lower()
    if lowered.startswith(
        (
            "http://",
            "https://",
            "about:",
            "data:",
            "file:",
            "chrome-extension://",
            "chrome://",
        )
    ):
        return url
    return f"https://{url}"
