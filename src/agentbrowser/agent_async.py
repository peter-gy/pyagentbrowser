from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

from agentbrowser._browser_common import is_stale_ref_error_code
from agentbrowser.command_params import click_params, wait_params
from agentbrowser.models import (
    ActionResult,
    ActionTransitionError,
    BrowserError,
    ConfirmationRequired,
    LoadState,
    MouseButton,
    NativeParseError,
    SnapshotData,
    SnapshotDiff,
    SnapshotRef,
    SnapshotSpec,
    Wait,
    diff_snapshot_data,
)

if TYPE_CHECKING:
    from agentbrowser.domains_async import AsyncFrame


class AsyncStaleRefError(BrowserError):
    """Raised when an async action targets a ref from an expired snapshot."""

    def __init__(self, ref: AsyncRef, error: BrowserError | None = None) -> None:
        if error is None:
            super().__init__(
                "ref",
                f"stale snapshot generation for {ref.selector}",
                {},
                code="stale_ref",
            )
        else:
            super().__init__(
                error.action,
                f"stale snapshot ref {ref.selector}: {error}",
                error.response,
                code=error.code,
            )
        self.ref = ref

    async def refresh(self, **criteria: Any) -> AsyncRef:
        """Resolve the ref again from a fresh snapshot."""
        return await self.ref.refresh(**criteria)


@dataclass(frozen=True, slots=True)
class _AsyncRefGenerationController:
    controller: Any
    ref: AsyncRef

    async def _command(self, action: str, **params: Any) -> Any:
        params["_refGeneration"] = self.ref.snapshot.generation
        try:
            return await self.controller._command(action, **params)
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise AsyncStaleRefError(self.ref, error) from error
            raise

    def __getattr__(self, name: str) -> Any:
        return getattr(self.controller, name)


@dataclass(frozen=True, slots=True)
class _AsyncRefPendingAction:
    pending: Any
    ref: AsyncRef

    @property
    def confirmation_id(self) -> str:
        return cast(str, self.pending.confirmation_id)

    @property
    def action(self) -> str:
        return cast(str, self.pending.action)

    @property
    def details(self) -> Any:
        return self.pending.details

    async def confirm(self) -> Any:
        try:
            return await self.pending.confirm()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = _AsyncRefPendingAction(error.pending, self.ref)
            raise
        except AsyncStaleRefError:
            raise
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise AsyncStaleRefError(self.ref, error) from error
            raise

    async def deny(self) -> None:
        await self.pending.deny()

    def map(self, complete: Any) -> _AsyncRefPendingAction:
        return _AsyncRefPendingAction(self.pending.map(complete), self.ref)


@dataclass(frozen=True, slots=True)
class AsyncRef:
    """Async element identity bound to one accessibility snapshot."""

    snapshot: AsyncSnapshot
    _ref: SnapshotRef

    @property
    def browser(self) -> Any:
        """Browser that captured this ref."""
        return self.snapshot.browser

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
        refreshed = await self.snapshot.refresh()
        return refreshed.one(
            role=self.role if role is None else role,
            name=self.name if name is None and contains is None else name,
            contains=contains,
            exact=exact,
        )

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
        source = self.snapshot.browser
        frames = getattr(source, "frames", None)
        if frames is None:
            raise TypeError("the snapshot is not bound to a page or frame handle")
        owner = replace(
            source,
            browser=_AsyncRefGenerationController(source.browser.controller, self),
        )
        try:
            frame = await owner.frames.get(selector=self.selector)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = _AsyncRefPendingAction(
                    error.pending.map(self._content_frame_result),
                    self,
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
        return replace(
            frame,
            browser=self.snapshot.browser.browser.controller,
        )

    async def text(self) -> str:
        """Return text content for the ref."""
        self._ensure_current()
        return await self._command(
            "gettext",
            _decode=lambda data: _string_field(data, "text", action="gettext"),
            selector=self.selector,
        )

    async def inner_text(self) -> str:
        """Return rendered text for the ref."""
        self._ensure_current()
        return await self._command(
            "innertext",
            _decode=lambda data: _string_field(data, "text", action="innertext"),
            selector=self.selector,
        )

    async def input_value(self) -> str:
        """Return the current form value."""
        self._ensure_current()
        return await self._command(
            "inputvalue",
            _decode=lambda data: _string_field(data, "value", action="inputvalue"),
            selector=self.selector,
        )

    async def attribute(self, name: str) -> str | None:
        """Return one attribute value."""
        self._ensure_current()
        return await self._command(
            "getattribute",
            _decode=_optional_attribute,
            selector=self.selector,
            attribute=name,
        )

    async def is_visible(self) -> bool:
        """Return whether the ref is visible."""
        self._ensure_current()
        return await self._command(
            "isvisible",
            _decode=lambda data: _bool_field(data, "visible", action="isvisible"),
            selector=self.selector,
        )

    async def is_enabled(self) -> bool:
        """Return whether the ref is enabled."""
        self._ensure_current()
        return await self._command(
            "isenabled",
            _decode=lambda data: _bool_field(data, "enabled", action="isenabled"),
            selector=self.selector,
        )

    async def is_checked(self) -> bool:
        """Return whether the ref is checked."""
        self._ensure_current()
        return await self._command(
            "ischecked",
            _decode=lambda data: _bool_field(data, "checked", action="ischecked"),
            selector=self.selector,
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
            await self._command(action, **params)

        return await self._transition(action, run, wait=wait)

    async def _command(self, action: str, **params: Any) -> Any:
        self._ensure_current()
        params["_refGeneration"] = self.snapshot.generation
        try:
            return await self.browser._command(action, **params)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = _AsyncRefPendingAction(error.pending, self)
            raise
        except BrowserError as error:
            if is_stale_ref_error_code(error.code):
                raise AsyncStaleRefError(self, error) from error
            raise

    def _ensure_current(self) -> None:
        controller = getattr(getattr(self.snapshot.browser, "browser", None), "controller", None)
        current = getattr(controller, "_ref_generation", self.snapshot.generation)
        if current != self.snapshot.generation:
            raise AsyncStaleRefError(self)

    async def _transition(
        self,
        action: str,
        run: Any,
        *,
        wait: Wait | None,
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        try:
            await run()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: self._result(action, wait=wait))
            raise
        return await self._result(action, wait=wait)

    async def _result(
        self, action: str, *, wait: Wait | None
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        try:
            await _apply_wait(self.browser, wait)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(lambda _value: self._capture_result(action))
            raise
        except Exception as cause:
            raise ActionTransitionError(
                action=action,
                target=self,
                stage="wait",
                before=self.snapshot,
                after=None,
                cause=cause,
            ) from cause
        return await self._capture_result(action)

    async def _capture_result(self, action: str) -> ActionResult[AsyncRef, AsyncSnapshot]:
        try:
            after = await self.snapshot.refresh()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda captured: self._finish_result(action, captured)
                )
            raise
        except Exception as cause:
            raise ActionTransitionError(
                action=action,
                target=self,
                stage="snapshot",
                before=self.snapshot,
                after=None,
                cause=cause,
            ) from cause
        return self._finish_result(action, after)

    def _finish_result(
        self, action: str, after: AsyncSnapshot
    ) -> ActionResult[AsyncRef, AsyncSnapshot]:
        try:
            diff = diff_snapshot_data(self.snapshot._data, after._data)
        except Exception as cause:
            raise ActionTransitionError(
                action=action,
                target=self,
                stage="diff",
                before=self.snapshot,
                after=after,
                cause=cause,
            ) from cause
        return ActionResult(
            action=action,
            target=self,
            before=self.snapshot,
            after=after,
            diff=diff,
        )


@dataclass(frozen=True, slots=True)
class AsyncSnapshot:
    """Immutable accessibility snapshot bound to an async browser."""

    browser: Any
    _data: SnapshotData

    @property
    def text(self) -> str:
        """Human-readable accessibility tree."""
        return self._data.text

    @property
    def origin(self) -> str:
        """Page URL reported by the native engine."""
        return self._data.origin

    @property
    def url(self) -> str:
        """Page URL reported by the native engine."""
        return self.origin

    @property
    def spec(self) -> SnapshotSpec:
        """Capture specification used for this snapshot."""
        return self._data.spec

    @property
    def generation(self) -> int:
        """Return the controller ref generation captured by this snapshot."""
        return self._data.generation

    @property
    def raw(self) -> Mapping[str, Any]:
        """Native snapshot response data."""
        return self._data.raw

    def __repr__(self) -> str:
        return (
            f"AsyncSnapshot(origin={self.origin!r}, refs={len(self._data.refs)!r}, "
            f"spec={self.spec!r})"
        )

    @property
    def refs(self) -> Mapping[str, AsyncRef]:
        """Bound refs keyed by ref id."""
        return {ref_id: self.ref(ref_id) for ref_id in self._data.refs}

    def ref(self, ref_id: str) -> AsyncRef:
        """Bind one snapshot ref to this browser."""
        return AsyncRef(self, self._data.ref(ref_id))

    def one(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> AsyncRef:
        """Return one ref matching accessible metadata."""
        return AsyncRef(
            self,
            self._data.one_ref(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            ),
        )

    def all(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> tuple[AsyncRef, ...]:
        """Return all refs matching accessible metadata."""
        return tuple(
            AsyncRef(self, snapshot_ref)
            for snapshot_ref in self._data.find_refs(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            )
        )

    async def refresh(self) -> AsyncSnapshot:
        """Capture the same snapshot specification again."""
        return await self.browser.observe(self.spec)

    async def diff(self) -> SnapshotDiff:
        """Compare this snapshot with the current page state."""
        try:
            current = await self.refresh()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda after: diff_snapshot_data(self._data, after._data)
                )
            raise
        return diff_snapshot_data(self._data, current._data)


async def _apply_wait(browser: Any, wait: Wait | None) -> None:
    if wait is None:
        return
    if wait.kind == "all":
        await _apply_waits(browser, wait.conditions, timeout_ms=wait.timeout_ms)
        return
    await browser._command(
        "wait",
        _decode=lambda _data: None,
        **wait_params(
            None,
            text=wait.value if wait.kind == "text" else None,
            url=wait.value if wait.kind == "url" else None,
            load_state=cast(LoadState, wait.value) if wait.kind == "load" else None,
            timeout_ms=wait.timeout_ms,
        ),
    )


async def _apply_waits(
    browser: Any,
    conditions: tuple[Wait, ...],
    *,
    timeout_ms: int | None = None,
) -> None:
    deadline = None if timeout_ms is None else monotonic() + timeout_ms / 1000
    for index, condition in enumerate(conditions):
        if deadline is not None:
            remaining_ms = max(0, int((deadline - monotonic()) * 1000))
            condition = replace(
                condition,
                timeout_ms=(
                    remaining_ms
                    if condition.timeout_ms is None
                    else min(condition.timeout_ms, remaining_ms)
                ),
            )
        try:
            await _apply_wait(browser, condition)
        except ConfirmationRequired as error:
            remaining = conditions[index + 1 :]
            if remaining and error.pending is not None:
                error.pending = error.pending.map(
                    lambda _value, remaining=remaining: _apply_waits(
                        browser,
                        remaining,
                        timeout_ms=(
                            None
                            if deadline is None
                            else max(0, int((deadline - monotonic()) * 1000))
                        ),
                    )
                )
            raise


def _string_field(data: Mapping[str, Any], field: str, *, action: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise NativeParseError(f"{action} field '{field}' must be a string")
    return value


def _bool_field(data: Mapping[str, Any], field: str, *, action: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise NativeParseError(f"{action} field '{field}' must be a boolean")
    return value


def _optional_attribute(data: Mapping[str, Any]) -> str | None:
    value = data.get("value")
    if value is None:
        return None
    if not isinstance(value, str):
        raise NativeParseError("getattribute field 'value' must be a string or null")
    return value
