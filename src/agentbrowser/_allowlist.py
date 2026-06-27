from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast
from urllib.parse import urlparse

from agentbrowser._browser_common import normalize_url
from agentbrowser.models import BrowserError, JSONObject, JSONValue

DENIED_CODE = "allowed_domains"
URL_TARGET_FIELDS: dict[str, tuple[str, ...]] = {
    "addscript": ("url",),
    "addstyle": ("url",),
    "auth_save": ("url",),
    "credentials_set": ("url",),
    "diff_url": ("url1", "url2"),
    "navigate": ("url",),
    "pushstate": ("url",),
    "read": ("url",),
    "recording_start": ("url",),
    "tab_new": ("url",),
    "vitals": ("url",),
}
URL_PATTERN_FIELDS: dict[str, tuple[str, ...]] = {
    "frame": ("url",),
    "responsebody": ("url",),
    "route": ("url",),
    "unroute": ("url",),
    "wait": ("url",),
    "waitforurl": ("url",),
}


@dataclass(frozen=True, slots=True)
class PreparedCommand:
    command: JSONObject
    policy: DomainAllowlist
    cleanup_paths: tuple[Path, ...] = ()

    def cleanup(self) -> None:
        for path in self.cleanup_paths:
            path.unlink(missing_ok=True)


class DomainAllowlist:
    """Python-side command guard for the native `allowedDomains` option."""

    def __init__(self, domains: str | None = None) -> None:
        self._patterns = _parse_domain_list(domains)

    @property
    def is_empty(self) -> bool:
        return not self._patterns

    def prepare(self, command: JSONObject) -> PreparedCommand:
        prepared = dict(command)
        cleanup_paths: tuple[Path, ...] = ()
        action = str(prepared.get("action", ""))
        policy = self._policy_for_command(action, command)

        if not policy.is_empty:
            policy._validate_command(prepared)
            if action == "state_load":
                prepared, cleanup_paths = policy._prepare_state_load(prepared)
            elif action == "launch":
                prepared, cleanup_paths = policy._prepare_launch(prepared)

        return PreparedCommand(prepared, policy, cleanup_paths)

    def finish(self, command: JSONObject) -> DomainAllowlist:
        if command.get("action") != "launch":
            return self
        allowed_domains = command.get("allowedDomains")
        if isinstance(allowed_domains, str):
            return DomainAllowlist(allowed_domains)
        return self

    def filter_successful_response(self, command: JSONObject, data: JSONValue) -> JSONValue:
        if self.is_empty:
            return data

        action = command.get("action")
        if action == "cookies_get":
            return self._filter_cookies_get_response(command, data)
        if action != "state_save":
            return data

        unsafe_export_all = bool(command.get("unsafeExportAll"))
        if unsafe_export_all:
            return data
        if not isinstance(data, Mapping):
            return data
        response_data = cast(Mapping[str, Any], data)
        path = response_data.get("path")
        if isinstance(path, str):
            self.filter_state_file_in_place(Path(path), action="state_save")
        return data

    def check_url(self, action: str, url: str) -> None:
        parsed = urlparse(normalize_url(url))
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or host is None:
            self._deny(action, f"No hostname in URL: {url}")
        if not self.is_domain_allowed(host):
            self._deny(action, f"Domain '{host}' is not in the allowed domains list")

    def check_url_pattern(self, action: str, pattern: str) -> None:
        value = pattern.strip()
        if not value or value == "*":
            return
        host = _url_pattern_host(value)
        if host is None:
            return
        checked_host, requires_wildcard = _validated_url_pattern_host(
            action,
            value,
            host,
            deny=self._deny,
        )
        if requires_wildcard and not self._is_wildcard_domain_allowed(checked_host):
            self._deny(action, f"Domain '*.{checked_host}' is not in the allowed domains list")
        if not requires_wildcard and not self.is_domain_allowed(checked_host):
            self._deny(action, f"Domain '{checked_host}' is not in the allowed domains list")

    def is_domain_allowed(self, domain: str) -> bool:
        if self.is_empty:
            return True
        hostname = domain.strip().lstrip(".").lower()
        if not hostname:
            return False
        for pattern in self._patterns:
            if pattern.startswith("*."):
                suffix = pattern[2:]
                if hostname == suffix or hostname.endswith(f".{suffix}"):
                    return True
            elif hostname == pattern:
                return True
        return False

    def _is_wildcard_domain_allowed(self, domain: str) -> bool:
        hostname = domain.strip().lstrip(".").lower()
        if not hostname:
            return False
        for pattern in self._patterns:
            if not pattern.startswith("*."):
                continue
            suffix = pattern[2:]
            if hostname == suffix or hostname.endswith(f".{suffix}"):
                return True
        return False

    def filter_state_file_in_place(self, path: Path, *, action: str) -> None:
        state = self._filtered_state(path, action=action)
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    def _policy_for_command(self, action: str, command: Mapping[str, Any]) -> DomainAllowlist:
        if action != "launch":
            return self
        allowed_domains = command.get("allowedDomains")
        if isinstance(allowed_domains, str):
            return DomainAllowlist(allowed_domains)
        return self

    def _validate_command(self, command: Mapping[str, Any]) -> None:
        action = str(command.get("action", ""))
        for field in URL_TARGET_FIELDS.get(action, ()):
            url = command.get(field)
            if isinstance(url, str) and url:
                self.check_url(action, url)
        for field in URL_PATTERN_FIELDS.get(action, ()):
            pattern = command.get(field)
            if isinstance(pattern, str):
                self.check_url_pattern(action, pattern)

        if action == "cookies_get":
            urls = command.get("urls")
            if isinstance(urls, list):
                for url in urls:
                    if isinstance(url, str):
                        self.check_url(action, url)
        elif action == "cookies_set":
            self._validate_cookie_command(command)
        elif action == "cookies_clear":
            if not bool(command.get("unsafeClearAll")):
                self._deny(
                    "cookies_clear",
                    "cookies.clear requires unsafe_clear_all=True when allowed domains are set",
                )
        elif action == "permissions":
            origin = command.get("origin")
            if isinstance(origin, str):
                self.check_url(action, origin)

    def _filter_cookies_get_response(
        self,
        command: Mapping[str, Any],
        data: JSONValue,
    ) -> JSONValue:
        if bool(command.get("unsafeExportAll")) or not isinstance(data, Mapping):
            return data
        response = dict(cast(Mapping[str, Any], data))
        response["cookies"] = self._filtered_cookies(response.get("cookies"))
        return response

    def _validate_cookie_command(self, command: Mapping[str, Any]) -> None:
        cookies = command.get("cookies")
        if isinstance(cookies, list):
            targets = [cookie for cookie in cookies if isinstance(cookie, Mapping)]
        elif isinstance(cookies, Mapping):
            targets = [cookies]
        else:
            targets = [command]

        for cookie in targets:
            if not self._cookie_is_allowed(cookie, action="cookies_set", fail=True):
                self._deny(
                    "cookies_set",
                    "Cookie target cannot be validated against allowed domains",
                )

    def _prepare_launch(self, command: JSONObject) -> tuple[JSONObject, tuple[Path, ...]]:
        storage_state = command.get("storageState")
        if not isinstance(storage_state, str):
            return command, ()
        prepared_path = self.filtered_state_copy(Path(storage_state), action="launch")
        return {**command, "storageState": str(prepared_path)}, (prepared_path,)

    def _prepare_state_load(self, command: JSONObject) -> tuple[JSONObject, tuple[Path, ...]]:
        path = command.get("path")
        if not isinstance(path, str):
            self._deny("state_load", "state_load requires a path when allowed domains are set")
        if bool(command.get("unsafeImportAll")):
            return command, ()
        prepared_path = self.filtered_state_copy(Path(path), action="state_load")
        return {**command, "path": str(prepared_path)}, (prepared_path,)

    def filtered_state_copy(self, path: Path, *, action: str) -> Path:
        state = self._filtered_state(path, action=action)
        handle, raw_path = tempfile.mkstemp(prefix="pyagentbrowser-state-", suffix=".json")
        target = Path(raw_path)
        with open(handle, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, sort_keys=True)
            file.write("\n")
        return target

    def _filtered_state(self, path: Path, *, action: str) -> dict[str, Any]:
        if path.suffix == ".enc" or path.name.endswith(".json.enc"):
            self._deny(action, "Encrypted storage state cannot be filtered by allowed domains")
        try:
            raw = json.loads(path.read_text())
        except OSError as err:
            self._deny(action, f"Failed to read storage state from {path}: {err}")
        except json.JSONDecodeError as err:
            self._deny(action, f"Invalid storage state JSON in {path}: {err}")

        if not isinstance(raw, Mapping):
            self._deny(action, "Storage state file must contain a JSON object")

        state = dict(cast(Mapping[str, Any], raw))
        state["cookies"] = self._filtered_cookies(state.get("cookies"))
        state["origins"] = self._filtered_origins(state.get("origins"))
        return state

    def _filtered_cookies(self, value: object) -> list[Mapping[str, Any]]:
        if not isinstance(value, list):
            return []
        return [
            cookie_mapping
            for cookie in value
            if isinstance(cookie, Mapping)
            for cookie_mapping in [cast(Mapping[str, Any], cookie)]
            if self._cookie_is_allowed(cookie_mapping, action="state_load", fail=False)
        ]

    def _filtered_origins(self, value: object) -> list[Mapping[str, Any]]:
        if not isinstance(value, list):
            return []
        origins: list[Mapping[str, Any]] = []
        for origin in value:
            if not isinstance(origin, Mapping):
                continue
            origin_mapping = cast(Mapping[str, Any], origin)
            raw_origin = origin_mapping.get("origin")
            if isinstance(raw_origin, str) and self._url_is_allowed(raw_origin):
                origins.append(origin_mapping)
        return origins

    def _cookie_is_allowed(
        self,
        cookie: Mapping[str, Any],
        *,
        action: str,
        fail: bool,
    ) -> bool:
        url = cookie.get("url")
        if isinstance(url, str):
            if self._url_is_allowed(url):
                return True
            if fail:
                self.check_url(action, url)
            return False

        domain = cookie.get("domain")
        if isinstance(domain, str):
            allowed = self.is_domain_allowed(domain)
            if allowed:
                return True
            if fail:
                self._deny(
                    action,
                    f"Cookie domain '{domain}' is not in the allowed domains list",
                )
            return False

        return False

    def _url_is_allowed(self, url: str) -> bool:
        parsed = urlparse(normalize_url(url))
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname is not None
            and self.is_domain_allowed(parsed.hostname)
        )

    def _deny(self, action: str, message: str) -> NoReturn:
        raise BrowserError(
            action,
            message,
            {"success": False, "error": message, "code": DENIED_CODE},
            code=DENIED_CODE,
        )


def _parse_domain_list(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(part.strip().lower() for part in value.split(",") if part.strip())


def _url_pattern_host(value: str) -> str | None:
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        return parsed.hostname or ""
    if value.startswith("*://"):
        head = value[4:].split("/", 1)[0]
        return _host_from_pattern_head(head)
    if "://" in value:
        return ""
    if value.startswith("//"):
        head = value[2:].split("/", 1)[0]
        return _host_from_pattern_head(head)
    wildcard_prefix_stripped = value.lstrip("*")
    if wildcard_prefix_stripped.startswith("//"):
        head = wildcard_prefix_stripped[2:].split("/", 1)[0]
        return _host_from_pattern_head(head)
    wildcard_slash_host = _host_from_wildcard_slash_pattern(value)
    if wildcard_slash_host is not None:
        return wildcard_slash_host
    if value.startswith(("/", "**/")):
        return None
    head = value.split("/", 1)[0]
    wildcard_localhost = _host_from_wildcard_localhost_head(head)
    if wildcard_localhost is not None:
        return wildcard_localhost
    if "*" in head and "." not in head and ":" not in head:
        return None
    if head:
        return _host_from_pattern_head(head)
    return None


def _host_from_wildcard_slash_pattern(value: str) -> str | None:
    wildcard_stripped = value.lstrip("*")
    if not value.startswith("*") or not wildcard_stripped.startswith("/"):
        return None
    head = wildcard_stripped.lstrip("/").split("/", 1)[0]
    if not _pattern_head_looks_host_qualified(head):
        return None
    return _host_from_pattern_head(head)


def _pattern_head_looks_host_qualified(head: str) -> bool:
    host = _host_from_pattern_head(head).strip().lower().rstrip(".")
    return bool(host) and (
        head.startswith("[") or ":" in head or "." in host or host == "localhost"
    )


def _host_from_wildcard_localhost_head(head: str) -> str | None:
    if not head.startswith("*"):
        return None
    candidate = head.lstrip("*")
    if not candidate.lower().rstrip(".").startswith("localhost"):
        return None
    return head


def _host_from_pattern_head(head: str) -> str:
    without_auth = head.rsplit("@", 1)[-1]
    if without_auth.startswith("["):
        return without_auth.split("]", 1)[0].lstrip("[")
    return without_auth.split(":", 1)[0]


def _validated_url_pattern_host(
    action: str,
    pattern: str,
    host: str,
    *,
    deny: Callable[[str, str], NoReturn],
) -> tuple[str, bool]:
    hostname = host.strip().lower().rstrip(".")
    requires_wildcard = False
    if hostname.startswith("*."):
        hostname = hostname[2:]
        requires_wildcard = True
    elif "*" in hostname:
        deny(action, f"URL pattern '{pattern}' cannot be validated against allowed domains")
    if not hostname:
        deny(action, f"No hostname in URL pattern: {pattern}")
    return hostname, requires_wildcard
