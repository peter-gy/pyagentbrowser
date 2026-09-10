from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, cast

from agentbrowser.contracts.connection import normalize_url
from agentbrowser.contracts.decode import none, required_string
from agentbrowser.execution.commands import AsyncExecutor, Command
from agentbrowser.features.documents.base_async import _AsyncDocument
from agentbrowser.features.documents.codec import read_result_from_data
from agentbrowser.features.documents.models import LoadState
from agentbrowser.features.documents.params import read_params
from agentbrowser.features.documents.read import ReadMode, ReadResult

if TYPE_CHECKING:
    from agentbrowser.features.capture.api import AsyncCapture, AsyncFrameCapture


class AsyncPage(_AsyncDocument):
    """Async operations bound to one browser page and its main document."""

    @property
    def capture(self) -> AsyncCapture:
        """Return screenshot and PDF capture for this page."""
        from agentbrowser.features.capture.api import AsyncCapture

        return AsyncCapture(self._executor)

    async def open(
        self,
        url: str,
        *,
        wait_until: LoadState = "load",
    ) -> None:
        """Navigate the current page to a URL.

        Example:
            ```python
            await browser.page.open("https://example.com")
            print(await browser.page.title())
            ```

        Parameters
        ----------
        url
            Absolute URL or host-like value. Host-like values are normalized to
            `https://...`.
        wait_until
            Load state the native engine should wait for.

        """
        await self.execute(
            Command("navigate", {"url": normalize_url(url), "waitUntil": wait_until}, decode=none)
        )

    async def title(self) -> str:
        """Return the current page title."""
        return await self.execute(
            Command("title", {}, decode=lambda data: required_string(data, "title", action="title"))
        )

    async def url(self) -> str:
        """Return the current page URL."""
        return await self.execute(
            Command("url", {}, decode=lambda data: required_string(data, "url", action="url"))
        )

    async def content(self) -> str:
        """Return the current page HTML."""
        return await self.execute(
            Command(
                "content", {}, decode=lambda data: required_string(data, "html", action="content")
            )
        )

    async def set_content(self, html: str) -> None:
        """Replace the current page document with HTML."""
        await self.execute(Command("setcontent", {"html": html}, decode=none))

    async def read(
        self,
        url: str | None = None,
        *,
        mode: ReadMode | None = None,
        filter: str | None = None,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
        allowed_domains: Sequence[str] | None = None,
    ) -> ReadResult:
        """Return agent-readable content for a URL or the active page.

        Example:
            ```python
            result = await browser.page.read(
                "https://example.com",
                mode=ReadMode.markdown(require=True),
            )
            print(result.content)
            ```
        """
        normalized_url = normalize_url(url) if url is not None else None
        return await self.execute(
            Command(
                "read",
                {
                    **read_params(
                        normalized_url,
                        mode=mode,
                        filter=filter,
                        timeout_ms=timeout_ms,
                        headers=headers,
                        allowed_domains=allowed_domains,
                    )
                },
                decode=read_result_from_data,
            )
        )

    async def back(self) -> None:
        """Navigate back in history."""
        await self.execute(Command("back", {}, decode=none))

    async def forward(self) -> None:
        """Navigate forward in history."""
        await self.execute(Command("forward", {}, decode=none))

    async def reload(self) -> None:
        """Reload the current page."""
        await self.execute(Command("reload", {}, decode=none))


class AsyncFrame(_AsyncDocument):
    """Async operations bound to one child browsing context."""

    def __init__(
        self,
        _executor: AsyncExecutor,
        *,
        target_id: str | None = None,
        frame_id: str,
        frame_name: str = "",
        frame_url: str = "",
        parent_frame_id: str | None = None,
    ) -> None:
        resolved_frame = frame_id
        if not isinstance(resolved_frame, str) or not resolved_frame.strip():
            raise ValueError("frame_id must be a non-empty string")
        super().__init__(
            _executor,
            target_id=target_id,
            frame_id=resolved_frame,
            frame_name=frame_name,
            frame_url=frame_url,
            parent_frame_id=parent_frame_id,
        )

    @property
    def frame_id(self) -> str:
        """Return the child browsing context identity."""
        return cast(str, self._executor.scope.frame_id)

    @property
    def capture(self) -> AsyncFrameCapture:
        """Return screenshot capture for this frame."""
        from agentbrowser.features.capture.api import AsyncFrameCapture

        return AsyncFrameCapture(self._executor)
