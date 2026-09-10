from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentbrowser.contracts.decode import none, required_string
from agentbrowser.contracts.protocol import optional
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.scripts.source import exclusive_source


@dataclass(frozen=True, slots=True)
class Scripts:
    """JavaScript and stylesheet injection helpers."""

    executor: Executor

    def add_init(
        self,
        script: str | None = None,
        *,
        path: str | Path | None = None,
    ) -> str:
        """Add a script that runs before future page scripts."""
        source = exclusive_source("scripts.add_init", inline=script, path=path)
        return self._register_init(source)

    def _register_init(self, source: str) -> str:
        return self.executor.execute(
            Command(
                "addinitscript",
                {"script": source},
                decode=lambda data: required_string(data, "identifier", action="addinitscript"),
            )
        )

    def remove_init(self, identifier: str) -> None:
        """Remove a previously registered init script."""
        self.executor.execute(Command("removeinitscript", {"identifier": identifier}, decode=none))

    def add(
        self,
        script: str | None = None,
        *,
        url: str | None = None,
    ) -> None:
        """Inject JavaScript into the current page from source or URL."""
        if script is None and url is None:
            raise ValueError("scripts.add requires either script=... or url=...")
        if script is not None and url is not None:
            raise ValueError("scripts.add accepts script=... or url=..., not both")
        self.executor.execute(
            Command("addscript", {"script": optional(script), "url": optional(url)}, decode=none)
        )

    def add_style(
        self,
        content: str | None = None,
        *,
        url: str | None = None,
    ) -> None:
        """Inject CSS into the current page from source or URL."""
        if content is None and url is None:
            raise ValueError("scripts.add_style requires either content=... or url=...")
        if content is not None and url is not None:
            raise ValueError("scripts.add_style accepts content=... or url=..., not both")
        self.executor.execute(
            Command("addstyle", {"content": optional(content), "url": optional(url)}, decode=none)
        )


@dataclass(frozen=True, slots=True)
class AsyncScripts:
    """Async JavaScript and stylesheet injection helpers."""

    executor: AsyncExecutor

    async def add_init(
        self,
        script: str | None = None,
        *,
        path: str | Path | None = None,
    ) -> str:
        """Add a script that runs before future page scripts."""
        source = exclusive_source("scripts.add_init", inline=script, path=path)
        return await self._register_init(source)

    async def _register_init(self, source: str) -> str:
        return await self.executor.execute(
            Command(
                "addinitscript",
                {"script": source},
                decode=lambda data: required_string(data, "identifier", action="addinitscript"),
            )
        )

    async def remove_init(self, identifier: str) -> None:
        """Remove a previously registered init script."""
        await self.executor.execute(
            Command("removeinitscript", {"identifier": identifier}, decode=none)
        )

    async def add(
        self,
        script: str | None = None,
        *,
        url: str | None = None,
    ) -> None:
        """Inject JavaScript into the current page from source or URL."""
        if script is None and url is None:
            raise ValueError("scripts.add requires either script=... or url=...")
        if script is not None and url is not None:
            raise ValueError("scripts.add accepts script=... or url=..., not both")
        await self.executor.execute(
            Command("addscript", {"script": optional(script), "url": optional(url)}, decode=none)
        )

    async def add_style(
        self,
        content: str | None = None,
        *,
        url: str | None = None,
    ) -> None:
        """Inject CSS into the current page from source or URL."""
        if content is None and url is None:
            raise ValueError("scripts.add_style requires either content=... or url=...")
        if content is not None and url is not None:
            raise ValueError("scripts.add_style accepts content=... or url=..., not both")
        await self.executor.execute(
            Command("addstyle", {"content": optional(content), "url": optional(url)}, decode=none)
        )
