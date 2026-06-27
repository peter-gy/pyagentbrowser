from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pyagentbrowser.cdp.models import (
    AsyncContextPredicate,
    AsyncExecutionContext,
    AsyncFrame,
    ContextPredicate,
    ExecutionContext,
    Frame,
)

if TYPE_CHECKING:
    from pyagentbrowser.cdp.controller import AsyncCDPController, CDPController
    from pyagentbrowser.cdp.page import AsyncCDPPageSession, CDPPageSession


@dataclass(frozen=True, slots=True)
class CDPTarget:
    """Synchronous handle for a selected CDP target."""

    _controller: CDPController = field(repr=False, compare=False)
    label: str | None = None
    url: str | None = None
    target_id: str | None = None

    def frames(self) -> list[Frame]:
        """Return frames for this target."""
        return self._page().frames()

    def frame(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Frame:
        """Return one frame selected by iframe selector, name, or URL."""
        return self._page().frame(selector=selector, name=name, url=url)

    def contexts(
        self,
        *,
        frame: str | Frame | None = None,
        extension_id: str | None = None,
        predicate: ContextPredicate | None = None,
    ) -> list[ExecutionContext]:
        """Return execution contexts in this target."""
        page = self._page()
        return page.contexts(
            frame=page.resolve_frame(frame),
            extension_id=extension_id,
            predicate=predicate,
        )

    def evaluate(
        self,
        script: str,
        *,
        frame: str | Frame | None = None,
        extension_id: str | None = None,
        context: ExecutionContext | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in this target."""
        page = self._page()
        if context is not None:
            return page.evaluate(
                script,
                context=context,
                await_promise=await_promise,
                return_by_value=return_by_value,
            )
        return page.evaluate(
            script,
            frame=page.resolve_frame(frame),
            extension_id=extension_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    def _page(self) -> CDPPageSession:
        return self._controller._page_session(
            label=self.label,
            url=self.url,
            target_id=self.target_id,
        )


@dataclass(frozen=True, slots=True)
class AsyncCDPTarget:
    """Async handle for a selected CDP target."""

    _controller: AsyncCDPController = field(repr=False, compare=False)
    label: str | None = None
    url: str | None = None
    target_id: str | None = None

    async def frames(self) -> list[AsyncFrame]:
        """Return frames for this target."""
        return await (await self._page()).frames()

    async def frame(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> AsyncFrame:
        """Return one frame selected by iframe selector, name, or URL."""
        return await (await self._page()).frame(selector=selector, name=name, url=url)

    async def contexts(
        self,
        *,
        frame: str | AsyncFrame | None = None,
        extension_id: str | None = None,
        predicate: AsyncContextPredicate | None = None,
    ) -> list[AsyncExecutionContext]:
        """Return execution contexts in this target."""
        page = await self._page()
        return await page.contexts(
            frame=await page.resolve_frame(frame),
            extension_id=extension_id,
            predicate=predicate,
        )

    async def evaluate(
        self,
        script: str,
        *,
        frame: str | AsyncFrame | None = None,
        extension_id: str | None = None,
        context: AsyncExecutionContext | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in this target."""
        page = await self._page()
        if context is not None:
            return await page.evaluate(
                script,
                context=context,
                await_promise=await_promise,
                return_by_value=return_by_value,
            )
        return await page.evaluate(
            script,
            frame=await page.resolve_frame(frame),
            extension_id=extension_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    async def _page(self) -> AsyncCDPPageSession:
        return await self._controller._page_session(
            label=self.label,
            url=self.url,
            target_id=self.target_id,
        )
