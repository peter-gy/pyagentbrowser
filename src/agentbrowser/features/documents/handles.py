from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, cast

from agentbrowser.contracts.connection import normalize_url
from agentbrowser.contracts.decode import none, required_string
from agentbrowser.execution.commands import Command, Executor
from agentbrowser.features.documents.base import _Document
from agentbrowser.features.documents.codec import read_result_from_data
from agentbrowser.features.documents.models import LoadState
from agentbrowser.features.documents.params import read_params
from agentbrowser.features.documents.read import ReadMode, ReadResult

if TYPE_CHECKING:
    from agentbrowser.features.capture.api import Capture, FrameCapture


class Page(_Document):
    """Operations bound to one browser page and its main document."""

    @property
    def capture(self) -> Capture:
        """Return screenshot and PDF capture for this page."""
        from agentbrowser.features.capture.api import Capture

        return Capture(self._executor)

    def open(self, url: str, *, wait_until: LoadState = "load") -> None:
        """Navigate the current page to a URL.

        Example:
            ```python
            browser.page.open("https://example.com")
            print(browser.page.title())
            ```

        Parameters
        ----------
        url
            Absolute URL or host-like value. Host-like values are normalized to
            `https://...`.
        wait_until
            Load state the native engine should wait for.

        """
        self.execute(
            Command("navigate", {"url": normalize_url(url), "waitUntil": wait_until}, decode=none)
        )

    def title(self) -> str:
        """Return the current page title."""
        return self.execute(
            Command("title", {}, decode=lambda data: required_string(data, "title", action="title"))
        )

    def url(self) -> str:
        """Return the current page URL."""
        return self.execute(
            Command("url", {}, decode=lambda data: required_string(data, "url", action="url"))
        )

    def content(self) -> str:
        """Return the current page HTML."""
        return self.execute(
            Command(
                "content", {}, decode=lambda data: required_string(data, "html", action="content")
            )
        )

    def set_content(self, html: str) -> None:
        """Replace the current page document with HTML."""
        self.execute(Command("setcontent", {"html": html}, decode=none))

    def read(
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
            result = browser.page.read(
                "https://example.com",
                mode=ReadMode.markdown(require=True),
            )
            print(result.content)
            ```
        """
        normalized_url = normalize_url(url) if url is not None else None
        return self.execute(
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

    def back(self) -> None:
        """Navigate back in history."""
        self.execute(Command("back", {}, decode=none))

    def forward(self) -> None:
        """Navigate forward in history."""
        self.execute(Command("forward", {}, decode=none))

    def reload(self) -> None:
        """Reload the current page."""
        self.execute(Command("reload", {}, decode=none))


class Frame(_Document):
    """Operations bound to one child browsing context."""

    def __init__(
        self,
        _executor: Executor,
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
    def capture(self) -> FrameCapture:
        """Return screenshot capture for this frame."""
        from agentbrowser.features.capture.api import FrameCapture

        return FrameCapture(self._executor)
