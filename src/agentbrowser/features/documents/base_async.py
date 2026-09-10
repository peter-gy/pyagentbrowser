from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, TypeVar

from agentbrowser.contracts.decode import none
from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.contracts.protocol import optional
from agentbrowser.contracts.scope import DocumentScope
from agentbrowser.execution.commands import AsyncExecutor, Command
from agentbrowser.features.documents.commands import geometry
from agentbrowser.features.documents.models import ElementGeometry, LoadState, WaitSelectorState
from agentbrowser.features.documents.params import wait_params
from agentbrowser.features.evidence.models import SnapshotData, SnapshotSpec

if TYPE_CHECKING:
    from agentbrowser.features.documents.frames_async import AsyncFrames
    from agentbrowser.features.documents.scroll import AsyncScroll
    from agentbrowser.features.evidence.snapshots import AsyncSnapshot
    from agentbrowser.features.queries import AsyncQueries


T = TypeVar("T")


@dataclass(frozen=True, slots=True, init=False)
class _AsyncDocument:
    """Async operations shared by page and frame documents."""

    _executor: AsyncExecutor = field(repr=False)
    frame_name: str = ""
    frame_url: str = ""
    parent_frame_id: str | None = None

    @property
    def find(self) -> AsyncQueries:
        """Return live queries bound to this document."""
        from agentbrowser.features.queries import AsyncQueries

        return AsyncQueries(self._executor)

    @property
    def frames(self) -> AsyncFrames:
        """Return child-frame discovery bound to this document."""
        from agentbrowser.features.documents.frames_async import AsyncFrames

        return AsyncFrames(self)

    @property
    def scroll(self) -> AsyncScroll:
        """Return measured document and container scrolling."""
        from agentbrowser.features.documents.scroll import AsyncScroll

        return AsyncScroll(self)

    async def observe(self, spec: SnapshotSpec | None = None) -> AsyncSnapshot:
        """Capture an accessibility snapshot bound to this document."""
        from agentbrowser.features.evidence.codec import snapshot_from_data
        from agentbrowser.features.evidence.models import SnapshotSpec

        capture_spec = spec or SnapshotSpec()
        if self.frame_id is not None and capture_spec.selector is not None:
            raise TypeError("Async frame snapshots capture the selected frame document")
        try:
            data = await self._execute(
                Command(
                    "snapshot",
                    {
                        "selector": optional(capture_spec.selector),
                        "interactive": capture_spec.interactive,
                        "compact": capture_spec.compact,
                        "maxDepth": optional(capture_spec.max_depth),
                        "urls": capture_spec.urls,
                    },
                    decode=lambda value: snapshot_from_data(value, spec=capture_spec),
                )
            )
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(self._snapshot_result)
            raise
        return self._snapshot_result(data)

    def _snapshot_result(self, data: SnapshotData) -> AsyncSnapshot:
        from agentbrowser.features.evidence.snapshots import AsyncSnapshot

        executor = self._executor
        data = replace(
            data,
            generation=data.raw.get("refGeneration", executor.generation),
        )
        target_id = data.raw.get("targetId")
        owner = type(self)(
            executor,
            target_id=str(target_id) if isinstance(target_id, str) else self.target_id,
            frame_id=self.frame_id,
            frame_name=self.frame_name,
            frame_url=data.origin,
            parent_frame_id=self.parent_frame_id,
        )
        return AsyncSnapshot(owner, data)

    async def geometry(self, selector: str | None = None) -> ElementGeometry:
        """Measure bounds and overflow for the document or one element."""
        return await self._execute(geometry(self._executor, selector))

    async def title(self) -> str:
        """Return the current document title."""
        return str(await self.evaluate("document.title"))

    async def url(self) -> str:
        """Return the current document URL."""
        return str(await self.evaluate("location.href"))

    async def content(self) -> str:
        """Return the current document HTML."""
        return str(await self.evaluate("document.documentElement.outerHTML"))

    async def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in the current page context."""
        try:
            return (await self._evaluate_data(script)).get("result")
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda data: data.get("result"))
            raise

    async def _evaluate_data(self, script: str) -> Mapping[str, Any]:
        return await self._execute(
            Command("evaluate", {"script": script}, decode=lambda data: data)
        )

    async def ready(
        self,
        *,
        timeout_ms: int | None = None,
        min_text_length: int = 1,
    ) -> None:
        """Wait until the page has readable body text."""
        if min_text_length < 0:
            raise ValueError("min_text_length must be non-negative")
        await self.wait_for_function(
            f"document.body && document.body.innerText.length >= {min_text_length}",
            timeout_ms=timeout_ms,
        )

    async def wait_for_text(self, text: str, *, timeout_ms: int | None = None) -> None:
        """Wait until text appears."""
        await self._execute(
            Command("wait", {**wait_params(None, text=text, timeout_ms=timeout_ms)}, decode=none)
        )

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: WaitSelectorState = "visible",
        timeout_ms: int | None = None,
    ) -> None:
        """Wait for a selector to reach a state."""
        await self._execute(
            Command(
                "wait",
                {**wait_params(None, selector=selector, state=state, timeout_ms=timeout_ms)},
                decode=none,
            )
        )

    async def wait_for_url(self, pattern: str, *, timeout_ms: int | None = None) -> None:
        """Wait for the page URL to match a pattern."""
        await self._execute(
            Command("wait", {**wait_params(None, url=pattern, timeout_ms=timeout_ms)}, decode=none)
        )

    async def wait_for_function(self, predicate: str, *, timeout_ms: int | None = None) -> None:
        """Wait for a JavaScript predicate to become truthy."""
        await self._execute(
            Command(
                "wait",
                {**wait_params(None, predicate=predicate, timeout_ms=timeout_ms)},
                decode=none,
            )
        )

    async def wait_for_load_state(self, state: LoadState = "load") -> None:
        """Wait for a page load state."""
        await self._execute(Command("wait", {**wait_params(None, load_state=state)}, decode=none))

    @property
    def scope(self) -> DocumentScope:
        scope = self._executor.scope
        return DocumentScope(
            scope.target_id, scope.frame_id, self.frame_url or scope.url, self._executor.generation
        )

    def __init__(
        self,
        _executor: AsyncExecutor,
        *,
        target_id: str | None = None,
        frame_id: str | None = None,
        frame_name: str = "",
        frame_url: str = "",
        parent_frame_id: str | None = None,
    ) -> None:
        inherited = _executor.scope
        scope = DocumentScope(
            target_id if target_id is not None else inherited.target_id,
            frame_id if frame_id is not None else inherited.frame_id,
            frame_url or inherited.url,
        )
        object.__setattr__(self, "_executor", _executor.bind(scope))
        object.__setattr__(self, "frame_name", frame_name)
        object.__setattr__(self, "frame_url", frame_url)
        object.__setattr__(self, "parent_frame_id", parent_frame_id)

    @property
    def target_id(self) -> str | None:
        """Return the browser target retained by this document."""
        return self._executor.scope.target_id

    @property
    def frame_id(self) -> str | None:
        """Return the child frame identity, or None for a page."""
        return self._executor.scope.frame_id

    async def _execute(self, command: Command[T]) -> T:
        return await self._executor.execute(command)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(target_id={self.target_id!r}, frame_id={self.frame_id!r})"
