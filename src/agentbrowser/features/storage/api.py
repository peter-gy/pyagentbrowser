from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentbrowser.contracts.decode import none, required_path
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.storage.codec import cookies_from_data
from agentbrowser.features.storage.models import Cookie, SameSite, StorageArea
from agentbrowser.features.storage.params import (
    cookies_clear_params,
    cookies_get_params,
    cookies_set_params,
    state_path_params,
    storage_clear_params,
    storage_get_params,
    storage_set_params,
)


@dataclass(frozen=True, slots=True)
class Cookies:
    """Cookie import, export, and clearing helpers."""

    executor: Executor

    def get(
        self,
        urls: Sequence[str] | None = None,
        *,
        unsafe_export_all: bool = False,
    ) -> tuple[Cookie, ...]:
        """Return cookies visible to the selected URLs."""
        return self.executor.execute(
            Command(
                "cookies_get",
                {**cookies_get_params(urls, unsafe_export_all=unsafe_export_all)},
                decode=cookies_from_data,
            )
        )

    def set(
        self,
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
    ) -> None:
        """Set one cookie or a sequence of cookie dictionaries."""
        self.executor.execute(
            Command(
                "cookies_set",
                {
                    **cookies_set_params(
                        name=name,
                        value=value,
                        cookies=cookies,
                        url=url,
                        domain=domain,
                        path=path,
                        expires=expires,
                        http_only=http_only,
                        secure=secure,
                        same_site=same_site,
                    )
                },
                decode=none,
            )
        )

    def clear(self, *, unsafe_clear_all: bool = False) -> None:
        """Clear browser cookies."""
        self.executor.execute(
            Command(
                "cookies_clear",
                {**cookies_clear_params(unsafe_clear_all=unsafe_clear_all)},
                decode=none,
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncCookies:
    """Async cookie import, export, and clearing helpers."""

    executor: AsyncExecutor

    async def get(
        self,
        urls: Sequence[str] | None = None,
        *,
        unsafe_export_all: bool = False,
    ) -> tuple[Cookie, ...]:
        """Return cookies visible to the selected URLs."""
        return await self.executor.execute(
            Command(
                "cookies_get",
                {**cookies_get_params(urls, unsafe_export_all=unsafe_export_all)},
                decode=cookies_from_data,
            )
        )

    async def set(
        self,
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
    ) -> None:
        """Set one cookie or a sequence of cookie dictionaries."""
        await self.executor.execute(
            Command(
                "cookies_set",
                {
                    **cookies_set_params(
                        name=name,
                        value=value,
                        cookies=cookies,
                        url=url,
                        domain=domain,
                        path=path,
                        expires=expires,
                        http_only=http_only,
                        secure=secure,
                        same_site=same_site,
                    )
                },
                decode=none,
            )
        )

    async def clear(self, *, unsafe_clear_all: bool = False) -> None:
        """Clear browser cookies."""
        await self.executor.execute(
            Command(
                "cookies_clear",
                {**cookies_clear_params(unsafe_clear_all=unsafe_clear_all)},
                decode=none,
            )
        )


@dataclass(frozen=True, slots=True)
class Storage:
    """Local and session storage helpers."""

    executor: Executor

    def get(self, key: str | None = None, *, area: StorageArea = "local") -> Any:
        """Return one storage value or the whole storage area."""
        return self.executor.execute(
            Command(
                "storage_get",
                {**storage_get_params(key, area=area)},
                decode=lambda data: data.get("value") if key is not None else data.get("data", {}),
            )
        )

    def set(self, key: str, value: str, *, area: StorageArea = "local") -> None:
        """Set one storage value."""
        self.executor.execute(
            Command("storage_set", {**storage_set_params(key, value, area=area)}, decode=none)
        )

    def clear(self, *, area: StorageArea = "local") -> None:
        """Clear a storage area."""
        self.executor.execute(
            Command("storage_clear", {**storage_clear_params(area=area)}, decode=none)
        )


@dataclass(frozen=True, slots=True)
class AsyncStorage:
    """Async local and session storage helpers."""

    executor: AsyncExecutor

    async def get(self, key: str | None = None, *, area: StorageArea = "local") -> Any:
        """Return one storage value or the whole storage area."""
        return await self.executor.execute(
            Command(
                "storage_get",
                {**storage_get_params(key, area=area)},
                decode=lambda data: data.get("value") if key is not None else data.get("data", {}),
            )
        )

    async def set(self, key: str, value: str, *, area: StorageArea = "local") -> None:
        """Set one storage value."""
        await self.executor.execute(
            Command("storage_set", {**storage_set_params(key, value, area=area)}, decode=none)
        )

    async def clear(self, *, area: StorageArea = "local") -> None:
        """Clear a storage area."""
        await self.executor.execute(
            Command("storage_clear", {**storage_clear_params(area=area)}, decode=none)
        )


@dataclass(frozen=True, slots=True)
class State:
    """Browser storage-state save, load, and maintenance helpers."""

    executor: Executor

    def save(self, path: str | Path | None = None, *, unsafe_export_all: bool = False) -> Path:
        """Save browser storage state and return the written file path."""
        return self.executor.execute(
            Command(
                "state_save",
                {**state_path_params(path, unsafeExportAll=unsafe_export_all)},
                decode=lambda data: required_path(data, action="state_save"),
            )
        )

    def load(self, path: str | Path, *, unsafe_import_all: bool = False) -> None:
        """Load browser storage state from a file.

        Raises `BrowserError` when the session uses `allowed_domains`.
        """
        self.executor.execute(
            Command(
                "state_load",
                {**state_path_params(path, unsafeImportAll=unsafe_import_all)},
                decode=none,
            )
        )

    def list(self) -> Mapping[str, Any]:
        """List saved storage states."""
        return self.executor.execute(Command("state_list", {}))

    def show(self, path: str | Path) -> Mapping[str, Any]:
        """Show metadata for a saved storage state."""
        return self.executor.execute(Command("state_show", {**state_path_params(path)}))

    def clear(self, path: str | Path | None = None) -> None:
        """Clear one saved state or all saved states."""
        self.executor.execute(Command("state_clear", {**state_path_params(path)}, decode=none))

    def clean(self, *, days: int = 30) -> None:
        """Delete saved states older than a number of days."""
        self.executor.execute(Command("state_clean", {"days": days}, decode=none))

    def rename(self, path: str | Path, name: str) -> None:
        """Rename a saved storage state."""
        self.executor.execute(
            Command("state_rename", {**state_path_params(path, name=name)}, decode=none)
        )


@dataclass(frozen=True, slots=True)
class AsyncState:
    """Async browser storage-state save, load, and maintenance helpers."""

    executor: AsyncExecutor

    async def save(
        self,
        path: str | Path | None = None,
        *,
        unsafe_export_all: bool = False,
    ) -> Path:
        """Save browser storage state and return the written file path."""
        return await self.executor.execute(
            Command(
                "state_save",
                {**state_path_params(path, unsafeExportAll=unsafe_export_all)},
                decode=lambda data: required_path(data, action="state_save"),
            )
        )

    async def load(self, path: str | Path, *, unsafe_import_all: bool = False) -> None:
        """Load browser storage state from a file.

        Raises `BrowserError` when the session uses `allowed_domains`.
        """
        await self.executor.execute(
            Command(
                "state_load",
                {**state_path_params(path, unsafeImportAll=unsafe_import_all)},
                decode=none,
            )
        )

    async def list(self) -> Mapping[str, Any]:
        """List saved storage states."""
        return await self.executor.execute(Command("state_list", {}))

    async def show(self, path: str | Path) -> Mapping[str, Any]:
        """Show metadata for a saved storage state."""
        return await self.executor.execute(Command("state_show", {**state_path_params(path)}))

    async def clear(self, path: str | Path | None = None) -> None:
        """Clear one saved state or all saved states."""
        await self.executor.execute(
            Command("state_clear", {**state_path_params(path)}, decode=none)
        )

    async def clean(self, *, days: int = 30) -> None:
        """Delete saved states older than a number of days."""
        await self.executor.execute(Command("state_clean", {"days": days}, decode=none))

    async def rename(self, path: str | Path, name: str) -> None:
        """Rename a saved storage state."""
        await self.executor.execute(
            Command("state_rename", {**state_path_params(path, name=name)}, decode=none)
        )
