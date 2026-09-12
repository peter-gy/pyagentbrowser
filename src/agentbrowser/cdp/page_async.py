from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.cdp._protocol import (
    _evaluate_params,
    _is_stale_context_error,
    _runtime_evaluate_value,
)
from agentbrowser.cdp._resolution import (
    _async_context_from_event,
    _context_matches_extension,
    _extract_frame_id,
    _frame_records,
    _single_context,
    _single_frame,
)
from agentbrowser.cdp.errors import (
    CDPFrameNotFoundError,
    CDPProtocolError,
    CDPStaleObjectError,
)
from agentbrowser.cdp.models import (
    AsyncContextPredicate,
    AsyncExecutionContext,
    AsyncFrame,
)
from agentbrowser.cdp.transport import AsyncCDPTransport


class AsyncCDPPageSession:
    """Async CDP session attached to one page target."""

    def __init__(self, client: AsyncCDPTransport, *, session_id: str, target_id: str) -> None:
        self._client = client
        self.session_id = session_id
        self.target_id = target_id
        self._generation = 0
        self._contexts: dict[tuple[str, int], AsyncExecutionContext] = {}
        self._frames: dict[str, AsyncFrame] = {}
        self._main_frame_id: str | None = None

    async def enable(self) -> None:
        """Enable required CDP domains and load initial frame/context state."""
        await self._client.send("Page.enable", session_id=self.session_id)
        await self._client.send("DOM.enable", session_id=self.session_id)
        await self._client.send("Runtime.enable", session_id=self.session_id)
        self._process_events(await self._client.drain_events())
        await self._refresh_frames()

    def invalidate(self) -> None:
        """Clear cached frame and execution context state."""
        self._generation += 1
        self._contexts.clear()
        self._frames.clear()
        self._main_frame_id = None

    async def resolve_frame(self, frame: str | AsyncFrame | None) -> AsyncFrame:
        """Resolve `None`, a selector string, or an existing frame handle."""
        if frame is None:
            return await self.frame()
        if isinstance(frame, AsyncFrame):
            self._check_frame(frame)
            return frame
        return await self.frame(selector=frame)

    async def frames(self) -> list[AsyncFrame]:
        """Return known frames after processing pending CDP events."""
        await self._sync()
        return list(self._frames.values())

    async def frame(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> AsyncFrame:
        """Return one frame selected by selector, name, URL, or main-frame default."""
        await self._sync()
        if selector is not None:
            return await self._frame_by_selector(selector)

        frames = (
            list(self._frames.values())
            if self._frames
            else list((await self._refresh_frames()).values())
        )
        if name is not None:
            frames = [frame for frame in frames if frame.name == name]
        if url is not None:
            frames = [frame for frame in frames if frame.url == url]
        if name is None and url is None:
            if self._main_frame_id is None:
                await self._refresh_frames()
            if self._main_frame_id is None:
                raise CDPFrameNotFoundError("CDP did not report a main frame")
            return self._frames[self._main_frame_id]
        return cast(AsyncFrame, _single_frame(frames, name=name, url=url))

    async def contexts(
        self,
        *,
        frame: AsyncFrame,
        extension_id: str | None = None,
        predicate: AsyncContextPredicate | None = None,
    ) -> list[AsyncExecutionContext]:
        """Return execution contexts for a frame."""
        self._check_frame(frame)
        await self._sync()
        contexts = [
            context
            for context in self._contexts.values()
            if context.frame_id == frame.id and context._session_id == frame.session_id
        ]
        if extension_id is not None:
            contexts = [
                context for context in contexts if _context_matches_extension(context, extension_id)
            ]
        if predicate is not None:
            contexts = [context for context in contexts if predicate(context)]
        return contexts

    async def context(
        self,
        *,
        frame: AsyncFrame,
        extension_id: str | None = None,
        predicate: AsyncContextPredicate | None = None,
    ) -> AsyncExecutionContext:
        """Return one execution context for a frame."""
        contexts = await self.contexts(frame=frame, extension_id=extension_id, predicate=predicate)
        if extension_id is None and predicate is None:
            contexts = [context for context in contexts if context.is_default]
        return cast(
            AsyncExecutionContext,
            _single_context(contexts, frame_id=frame.id, extension_id=extension_id),
        )

    async def evaluate(
        self,
        script: str,
        *,
        frame: AsyncFrame | None = None,
        context: AsyncExecutionContext | None = None,
        extension_id: str | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in a frame or execution context."""
        if context is None:
            context = await self.context(
                frame=frame or await self.frame(), extension_id=extension_id
            )
        self._check_context(context)

        params = _evaluate_params(
            script,
            context_id=context.id,
            unique_id=context.unique_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

        try:
            data = await self._client.send(
                "Runtime.evaluate",
                params,
                session_id=context._session_id,
            )
        except CDPProtocolError as err:
            if _is_stale_context_error(err):
                raise CDPStaleObjectError(
                    "execution context is stale. Take a fresh frame/context"
                ) from err
            raise
        return _runtime_evaluate_value(data)

    async def _sync(self) -> None:
        self._process_events(await self._client.drain_events())
        if not self._contexts:
            await self._client.send("Runtime.enable", session_id=self.session_id)
            self._process_events(await self._client.drain_events())
        if not self._frames:
            await self._refresh_frames()

    async def _refresh_frames(self) -> dict[str, AsyncFrame]:
        data = await self._client.send("Page.getFrameTree", session_id=self.session_id)
        frames: dict[str, AsyncFrame] = {}
        for raw_frame in _frame_records(data):
            frame = AsyncFrame(
                id=str(raw_frame.get("id", "")),
                name=str(raw_frame.get("name", "")),
                url=str(raw_frame.get("url", "")),
                session_id=self.session_id,
                _owner=self,
                _generation=self._generation,
            )
            if self._main_frame_id is None:
                self._main_frame_id = frame.id
            frames[frame.id] = frame
        self._frames = frames
        return frames

    async def _frame_by_selector(self, selector: str) -> AsyncFrame:
        document = await self._client.send(
            "DOM.getDocument",
            {"depth": 0, "pierce": True},
            session_id=self.session_id,
        )
        root = document.get("root")
        if not isinstance(root, Mapping):
            raise CDPFrameNotFoundError("CDP DOM.getDocument did not return a root node")
        node_id = (
            await self._client.send(
                "DOM.querySelector",
                {"nodeId": root.get("nodeId"), "selector": selector},
                session_id=self.session_id,
            )
        ).get("nodeId")
        if not isinstance(node_id, int) or node_id == 0:
            raise CDPFrameNotFoundError(f"no iframe matched selector {selector!r}")
        described = await self._client.send(
            "DOM.describeNode",
            {"nodeId": node_id, "depth": 0, "pierce": True},
            session_id=self.session_id,
        )
        frame_id = _extract_frame_id(described.get("node"))
        if frame_id is None:
            raise CDPFrameNotFoundError(f"selector {selector!r} did not resolve to a frame node")
        await self._refresh_frames()
        if frame_id in self._frames:
            return self._frames[frame_id]
        return AsyncFrame(
            id=frame_id,
            name="",
            url="",
            session_id=self.session_id,
            _owner=self,
            _generation=self._generation,
        )

    def _process_events(self, events: list[Mapping[str, Any]]) -> None:
        for event in events:
            session_id = event.get("sessionId")
            if session_id is not None and str(session_id) != self.session_id:
                continue
            method = event.get("method")
            params = event.get("params")
            if not isinstance(params, Mapping):
                params = {}
            if method == "Runtime.executionContextCreated":
                context = _async_context_from_event(params, self, self.session_id, self._generation)
                if context is not None:
                    self._contexts[(context._session_id, context.id)] = context
            elif method == "Runtime.executionContextDestroyed":
                context_id = params.get("executionContextId")
                if isinstance(context_id, int):
                    self._contexts.pop((self.session_id, context_id), None)
            elif method in {
                "Runtime.executionContextsCleared",
                "Page.frameNavigated",
                "Page.frameDetached",
            }:
                self.invalidate()

    def _check_frame(self, frame: AsyncFrame) -> None:
        if frame._owner is not self or frame._generation != self._generation:
            raise CDPStaleObjectError("frame is stale. Resolve it again after navigation")

    def _check_context(self, context: AsyncExecutionContext) -> None:
        if context._owner is not self or context._generation != self._generation:
            raise CDPStaleObjectError(
                "execution context is stale. Resolve it again after navigation"
            )
