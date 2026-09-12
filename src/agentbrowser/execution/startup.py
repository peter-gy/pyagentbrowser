from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentbrowser.contracts.actions import INTERNAL_SHUTDOWN_ACTION
from agentbrowser.contracts.protocol import OMIT
from agentbrowser.install import ensure_installed
from agentbrowser.launch import LaunchConfiguration, LaunchOptions

_SKIP_AUTO_INSTALL_ACTIONS = {
    "",
    INTERNAL_SHUTDOWN_ACTION,
    "close",
    "read",
    "har_stop",
    "credentials_set",
    "credentials_get",
    "credentials_delete",
    "credentials_list",
    "auth_save",
    "auth_show",
    "auth_delete",
    "auth_list",
    "confirm",
    "deny",
    "state_list",
    "state_show",
    "state_clear",
    "state_clean",
    "state_rename",
    "device_list",
    "stream_enable",
    "stream_disable",
    "stream_status",
    "session_info",
}


def _uses_local_chrome(params: Mapping[str, Any]) -> bool:
    if _present(params.get("executablePath")):
        return False
    if _present(params.get("provider")):
        return False
    if _present(params.get("cdpUrl")) or _present(params.get("cdpPort")):
        return False
    if bool(params.get("autoConnect")):
        return False
    engine = params.get("engine")
    if not _present(engine):
        engine = os.environ.get("AGENT_BROWSER_ENGINE")
    if _present(engine) and str(engine).lower() != "chrome":
        return False
    if os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH"):
        return False
    if os.environ.get("AGENT_BROWSER_CDP") or os.environ.get("AGENT_BROWSER_AUTO_CONNECT"):
        return False
    provider = os.environ.get("AGENT_BROWSER_PROVIDER")
    return provider is None or provider.strip().lower() in {"", "ios", "safari"}


def _present(value: Any) -> bool:
    return value is not None and value is not OMIT and value != ""


def requires_start(action: str, params: Mapping[str, object]) -> bool:
    return action in {"navigate", "addinitscript", "cdp_url"} or (
        action == "read" and params.get("url") in {None, OMIT}
    )


@dataclass
class Startup:
    configuration: LaunchConfiguration
    auto_install: bool
    installed: bool = False

    def launch_params(self, options: LaunchOptions | None = None) -> dict[str, Any]:
        params = self.configuration.command_params(options=options)
        self._prepare_launch(params)
        return params

    async def launch_params_async(self, options: LaunchOptions | None = None) -> dict[str, Any]:
        params = self.configuration.command_params(options=options)
        await asyncio.to_thread(self._prepare_launch, params)
        return params

    def _prepare_launch(self, params: dict[str, Any]) -> None:
        if self.auto_install and not self.installed and _uses_local_chrome(params):
            result = ensure_installed()
            params["executablePath"] = str(result.executable_path)
            self.installed = True

    def prepare_action(self, action: str, params: dict[str, Any], *, launched: bool) -> None:
        if not self.auto_install or self.installed or launched:
            return
        if action == "launch":
            self._prepare_launch(params)
            return
        if action in _SKIP_AUTO_INSTALL_ACTIONS:
            return
        if _uses_local_chrome(self.configuration.command_params()):
            ensure_installed()
            self.installed = True

    async def prepare_action_async(
        self,
        action: str,
        params: dict[str, Any],
        *,
        launched: bool,
    ) -> None:
        if not self.auto_install or self.installed or launched:
            return
        await asyncio.to_thread(self.prepare_action, action, params, launched=launched)
