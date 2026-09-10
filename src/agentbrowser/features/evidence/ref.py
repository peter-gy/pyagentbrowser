from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from agentbrowser.contracts.actions import is_stale_ref_error_code
from agentbrowser.contracts.errors import BrowserError, ConfirmationRequired
from agentbrowser.execution.commands import Command
from agentbrowser.features.evidence.changes import ActionResult
from agentbrowser.features.evidence.errors import StaleRefError, stale_error
from agentbrowser.features.evidence.fields import _bool_field, _optional_attribute, _string_field
from agentbrowser.features.evidence.models import SnapshotRef
from agentbrowser.features.evidence.transitions import transition
from agentbrowser.features.evidence.waits import Wait
from agentbrowser.features.input.models import MouseButton
from agentbrowser.features.input.params import click_params

if TYPE_CHECKING:
    from agentbrowser.features.documents.base import _Document
    from agentbrowser.features.documents.handles import Frame
    from agentbrowser.features.evidence.snapshots import Snapshot


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Ref:
    """Element identity bound to one accessibility snapshot."""

    snapshot: Snapshot
    _ref: SnapshotRef

    @property
    def document(self) -> _Document:
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
            f"Ref(selector={self.selector!r}, role={self.role!r}, name={self.name!r}, "
            f"origin={self.snapshot.origin!r})"
        )

    def refresh(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = True,
    ) -> Ref:
        """Resolve this element from a fresh snapshot."""

        def resolve(snapshot: Snapshot) -> Ref:
            return snapshot.one(
                role=self.role if role is None else role,
                name=self.name if name is None and contains is None else name,
                contains=contains,
                exact=exact,
            )

        try:
            refreshed = self.snapshot.refresh()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(resolve)
            raise
        return resolve(refreshed)

    def click(
        self,
        *,
        button: MouseButton = "left",
        click_count: int = 1,
        new_tab: bool = False,
        wait: Wait | None = None,
    ) -> ActionResult[Ref, Snapshot]:
        """Click the ref and return transition evidence."""
        return self._act(
            "click",
            click_params(
                self.selector,
                button=button,
                click_count=click_count,
                new_tab=new_tab,
            ),
            wait=wait,
        )

    def fill(self, value: str, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Fill the ref and return transition evidence."""
        return self._act(
            "fill",
            {"selector": self.selector, "value": value},
            wait=wait,
        )

    def type(self, text: str, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Type into the ref and return transition evidence."""
        return self._act(
            "type",
            {"selector": self.selector, "text": text},
            wait=wait,
        )

    def hover(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Hover the ref and return transition evidence."""
        return self._act("hover", {"selector": self.selector}, wait=wait)

    def tap(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Tap the ref and return transition evidence."""
        return self._act("tap", {"selector": self.selector}, wait=wait)

    def focus(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Focus the ref and return transition evidence."""
        return self._act("focus", {"selector": self.selector}, wait=wait)

    def clear(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Clear the ref and return transition evidence."""
        return self._act("clear", {"selector": self.selector}, wait=wait)

    def select(self, value: str, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Select an option and return transition evidence."""
        return self._act(
            "select",
            {"selector": self.selector, "value": value},
            wait=wait,
        )

    def check(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Check the ref and return transition evidence."""
        return self._act("check", {"selector": self.selector}, wait=wait)

    def uncheck(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Uncheck the ref and return transition evidence."""
        return self._act("uncheck", {"selector": self.selector}, wait=wait)

    def scroll_into_view(self, *, wait: Wait | None = None) -> ActionResult[Ref, Snapshot]:
        """Scroll the ref into view and return transition evidence."""
        return self._act("scrollintoview", {"selector": self.selector}, wait=wait)

    def content_frame(self) -> Frame:
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
            frame = owner.frames.get(selector=self.selector)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(self._content_frame_result).map_error(
                    lambda failure: stale_error(self, failure)
                )
            raise
        except StaleRefError:
            raise
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise StaleRefError(self, error) from error
            raise
        return self._content_frame_result(frame)

    def _content_frame_result(self, frame: Frame) -> Frame:
        return type(frame)(
            self.snapshot.document._executor,
            target_id=frame.target_id,
            frame_id=frame.frame_id,
            frame_name=frame.frame_name,
            frame_url=frame.frame_url,
            parent_frame_id=frame.parent_frame_id,
        )

    def text(self) -> str:
        """Return text content for the ref."""
        self._ensure_current()
        return self.execute(
            Command(
                "gettext",
                {"selector": self.selector},
                decode=lambda data: _string_field(data, "text", action="gettext"),
            )
        )

    def inner_text(self) -> str:
        """Return rendered text for the ref."""
        self._ensure_current()
        return self.execute(
            Command(
                "innertext",
                {"selector": self.selector},
                decode=lambda data: _string_field(data, "text", action="innertext"),
            )
        )

    def input_value(self) -> str:
        """Return the current form value."""
        self._ensure_current()
        return self.execute(
            Command(
                "inputvalue",
                {"selector": self.selector},
                decode=lambda data: _string_field(data, "value", action="inputvalue"),
            )
        )

    def attribute(self, name: str) -> str | None:
        """Return one attribute value."""
        self._ensure_current()
        return self.execute(
            Command(
                "getattribute",
                {"selector": self.selector, "attribute": name},
                decode=_optional_attribute,
            )
        )

    def is_visible(self) -> bool:
        """Return whether the ref is visible."""
        self._ensure_current()
        return self.execute(
            Command(
                "isvisible",
                {"selector": self.selector},
                decode=lambda data: _bool_field(data, "visible", action="isvisible"),
            )
        )

    def is_enabled(self) -> bool:
        """Return whether the ref is enabled."""
        self._ensure_current()
        return self.execute(
            Command(
                "isenabled",
                {"selector": self.selector},
                decode=lambda data: _bool_field(data, "enabled", action="isenabled"),
            )
        )

    def is_checked(self) -> bool:
        """Return whether the ref is checked."""
        self._ensure_current()
        return self.execute(
            Command(
                "ischecked",
                {"selector": self.selector},
                decode=lambda data: _bool_field(data, "checked", action="ischecked"),
            )
        )

    def _act(
        self,
        action: str,
        params: Mapping[str, Any],
        *,
        wait: Wait | None,
    ) -> ActionResult[Ref, Snapshot]:
        self._ensure_current()
        return transition(
            self,
            action,
            lambda: self.execute(Command(action, {**params})),
            wait=wait,
        )

    def execute(self, command: Command[T]) -> T:
        self._ensure_current()
        executor = self.document._executor.bind(
            self.document.scope, ref_generation=self.snapshot.generation
        )
        try:
            return executor.execute(command)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map_error(lambda failure: stale_error(self, failure))
            raise
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise StaleRefError(self, error) from error
            raise

    def _ensure_current(self) -> None:
        current = self.document._executor.generation
        if current != self.snapshot.generation:
            raise StaleRefError(self)
