from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from agentbrowser.contracts.actions import is_stale_ref_error_code
from agentbrowser.contracts.errors import BrowserError, ConfirmationRequired
from agentbrowser.execution.commands import Command
from agentbrowser.features.evidence.changes import ActionResult
from agentbrowser.features.evidence.errors import AsyncStaleRefError, async_stale_error
from agentbrowser.features.evidence.fields import _bool_field, _optional_attribute, _string_field
from agentbrowser.features.evidence.models import SnapshotRef
from agentbrowser.features.evidence.transitions_async import transition
from agentbrowser.features.evidence.waits import Wait
from agentbrowser.features.input.models import MouseButton
from agentbrowser.features.input.params import click_params

if TYPE_CHECKING:
    from agentbrowser.features.documents.base_async import _AsyncDocument
    from agentbrowser.features.documents.handles_async import AsyncFrame
    from agentbrowser.features.evidence.snapshots import AsyncSnapshot


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AsyncRef:
    """Async element identity bound to one accessibility snapshot."""

    snapshot: AsyncSnapshot
    _ref: SnapshotRef

    @property
    def document(self) -> _AsyncDocument:
        """Document that captured this ref."""
        return self.snapshot.document

    @property
    def id(self) -> str:
        """Ref id without the leading ``@``."""
        return self._ref.id

    @property
    def selector(self) -> str:
        """Native selector for this ref."""
        return self._ref.selector

    @property
    def role(self) -> str:
        """Accessible role captured in the snapshot."""
        return self._ref.role

    @property
    def name(self) -> str:
        """Accessible name captured in the snapshot."""
        return self._ref.name

    @property
    def raw(self) -> Mapping[str, Any]:
        """Native ref metadata."""
        return self._ref.raw

    def __repr__(self) -> str:
        return (
            f"AsyncRef(selector={self.selector!r}, role={self.role!r}, name={self.name!r}, "
            f"origin={self.snapshot.origin!r})"
        )

    async def refresh(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = True,
    ) -> AsyncRef:
        """Resolve this element from a fresh snapshot."""

        def resolve(snapshot: AsyncSnapshot) -> AsyncRef:
            return snapshot.one(
                role=self.role if role is None else role,
                name=self.name if name is None and contains is None else name,
                contains=contains,
                exact=exact,
            )

        try:
            refreshed = await self.snapshot.refresh()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(resolve)
            raise
        return resolve(refreshed)

    async def click(
        self,
        *,
        button: MouseButton = "left",
        click_count: int = 1,
        new_tab: bool = False,
        wait: Wait | None = None,
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Click the ref and return transition evidence."""
        return await self._act(
            "click",
            click_params(
                self.selector,
                button=button,
                click_count=click_count,
                new_tab=new_tab,
            ),
            wait=wait,
        )

    async def fill(
        self, value: str, *, wait: Wait | None = None
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Fill the ref and return transition evidence."""
        return await self._act(
            "fill",
            {"selector": self.selector, "value": value},
            wait=wait,
        )

    async def type(
        self, text: str, *, wait: Wait | None = None
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Type into the ref and return transition evidence."""
        return await self._act(
            "type",
            {"selector": self.selector, "text": text},
            wait=wait,
        )

    async def hover(self, *, wait: Wait | None = None) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Hover the ref and return transition evidence."""
        return await self._act("hover", {"selector": self.selector}, wait=wait)

    async def tap(self, *, wait: Wait | None = None) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Tap the ref and return transition evidence."""
        return await self._act("tap", {"selector": self.selector}, wait=wait)

    async def focus(self, *, wait: Wait | None = None) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Focus the ref and return transition evidence."""
        return await self._act("focus", {"selector": self.selector}, wait=wait)

    async def clear(self, *, wait: Wait | None = None) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Clear the ref and return transition evidence."""
        return await self._act("clear", {"selector": self.selector}, wait=wait)

    async def select(
        self, value: str, *, wait: Wait | None = None
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Select an option and return transition evidence."""
        return await self._act(
            "select",
            {"selector": self.selector, "value": value},
            wait=wait,
        )

    async def check(self, *, wait: Wait | None = None) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Check the ref and return transition evidence."""
        return await self._act("check", {"selector": self.selector}, wait=wait)

    async def uncheck(self, *, wait: Wait | None = None) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Uncheck the ref and return transition evidence."""
        return await self._act("uncheck", {"selector": self.selector}, wait=wait)

    async def scroll_into_view(
        self, *, wait: Wait | None = None
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        """Scroll the ref into view and return transition evidence."""
        return await self._act("scrollintoview", {"selector": self.selector}, wait=wait)

    async def content_frame(self) -> AsyncFrame:
        """Return the child frame owned by this inspected iframe element."""
        self._ensure_current()
        source = self.snapshot.document
        owner = type(source)(
            source._executor.bind(source.scope, ref_generation=self.snapshot.generation),
            target_id=source.target_id,
            frame_id=source.frame_id,
            frame_name=source.frame_name,
            frame_url=source.frame_url,
            parent_frame_id=source.parent_frame_id,
        )
        try:
            frame = await owner.frames.get(selector=self.selector)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(self._content_frame_result).map_error(
                    lambda failure: async_stale_error(self, failure)
                )
            raise
        except AsyncStaleRefError:
            raise
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise AsyncStaleRefError(self, error) from error
            raise
        return self._content_frame_result(frame)

    def _content_frame_result(self, frame: AsyncFrame) -> AsyncFrame:
        return type(frame)(
            self.snapshot.document._executor,
            target_id=frame.target_id,
            frame_id=frame.frame_id,
            frame_name=frame.frame_name,
            frame_url=frame.frame_url,
            parent_frame_id=frame.parent_frame_id,
        )

    async def text(self) -> str:
        """Return text content for the ref."""
        self._ensure_current()
        return await self._execute(
            Command(
                "gettext",
                {"selector": self.selector},
                decode=lambda data: _string_field(data, "text", action="gettext"),
            )
        )

    async def inner_text(self) -> str:
        """Return rendered text for the ref."""
        self._ensure_current()
        return await self._execute(
            Command(
                "innertext",
                {"selector": self.selector},
                decode=lambda data: _string_field(data, "text", action="innertext"),
            )
        )

    async def input_value(self) -> str:
        """Return the current form value."""
        self._ensure_current()
        return await self._execute(
            Command(
                "inputvalue",
                {"selector": self.selector},
                decode=lambda data: _string_field(data, "value", action="inputvalue"),
            )
        )

    async def attribute(self, name: str) -> str | None:
        """Return one attribute value."""
        self._ensure_current()
        return await self._execute(
            Command(
                "getattribute",
                {"selector": self.selector, "attribute": name},
                decode=_optional_attribute,
            )
        )

    async def is_visible(self) -> bool:
        """Return whether the ref is visible."""
        self._ensure_current()
        return await self._execute(
            Command(
                "isvisible",
                {"selector": self.selector},
                decode=lambda data: _bool_field(data, "visible", action="isvisible"),
            )
        )

    async def is_enabled(self) -> bool:
        """Return whether the ref is enabled."""
        self._ensure_current()
        return await self._execute(
            Command(
                "isenabled",
                {"selector": self.selector},
                decode=lambda data: _bool_field(data, "enabled", action="isenabled"),
            )
        )

    async def is_checked(self) -> bool:
        """Return whether the ref is checked."""
        self._ensure_current()
        return await self._execute(
            Command(
                "ischecked",
                {"selector": self.selector},
                decode=lambda data: _bool_field(data, "checked", action="ischecked"),
            )
        )

    async def _act(
        self,
        action: str,
        params: Mapping[str, Any],
        *,
        wait: Wait | None,
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        self._ensure_current()

        async def run() -> None:
            await self._execute(Command(action, {**params}))

        return await transition(self, action, run, wait=wait)

    async def _execute(self, command: Command[T]) -> T:
        self._ensure_current()
        executor = self.document._executor.bind(
            self.document.scope, ref_generation=self.snapshot.generation
        )
        try:
            return await executor.execute(command)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map_error(
                    lambda failure: async_stale_error(self, failure)
                )
            raise
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise AsyncStaleRefError(self, error) from error
            raise

    def _ensure_current(self) -> None:
        current = self.document._executor.generation
        if current != self.snapshot.generation:
            raise AsyncStaleRefError(self)
