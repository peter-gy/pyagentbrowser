from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from typing_extensions import Self

from pyagentbrowser._browser_common import is_stale_ref_error_code
from pyagentbrowser.command_params import click_params, wait_params
from pyagentbrowser.domains_async import AsyncLocator
from pyagentbrowser.models import (
    ActionEvidence,
    BrowserError,
    LoadState,
    MouseButton,
    Snapshot,
    SnapshotRef,
    WaitSelectorState,
    ref_selector,
)


class AsyncStaleAgentRefError(BrowserError):
    """Raised when an async action targets a stale snapshot ref."""

    def __init__(self, ref: AsyncAgentRef, error: BrowserError) -> None:
        super().__init__(
            error.action, f"stale snapshot ref {ref.selector}: {error}", error.response
        )
        self.ref = ref

    async def refresh(self, **criteria: Any) -> AsyncAgentRef:
        """Refresh the stale ref using optional match criteria."""
        return await self.ref.refresh(**criteria)


@dataclass(frozen=True, slots=True)
class AsyncAgentRef:
    """Async bound snapshot ref with direct element actions.

    `AsyncAgentRef` is returned by `AsyncAgentSnapshot.ref()`, `find()`, and
    `find_all()`. It keeps the snapshot selector, role, name, and browser needed
    to perform direct async element actions.
    """

    browser: Any
    snapshot_ref: SnapshotRef
    snapshot: Snapshot | None = None

    @property
    def id(self) -> str:
        """Snapshot ref id without the leading `@`."""
        return self.snapshot_ref.id

    @property
    def selector(self) -> str:
        """Native selector form, for example `@r1`."""
        return self.snapshot_ref.selector

    @property
    def role(self) -> str:
        """Accessible role captured in the snapshot."""
        return self.snapshot_ref.role

    @property
    def name(self) -> str:
        """Accessible name captured in the snapshot."""
        return self.snapshot_ref.name

    @property
    def raw(self) -> Mapping[str, Any]:
        """Raw snapshot ref metadata."""
        return self.snapshot_ref.raw

    def locator(self) -> AsyncLocator:
        """Return a lower-level async locator for this snapshot ref."""
        return AsyncLocator(self.browser, self.selector)

    async def refresh(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = True,
        strict: bool = True,
    ) -> AsyncAgentRef:
        """Re-find this ref in a fresh snapshot."""
        return (await self.browser.agent.observe()).find(
            role=self.role if role is None else role,
            name=self.name if name is None and contains is None else name,
            contains=contains,
            exact=exact,
            strict=strict,
        )

    async def click(
        self,
        *,
        button: MouseButton = "left",
        click_count: int = 1,
        new_tab: bool = False,
    ) -> Self:
        """Click this ref and return it."""
        return await self._run(
            lambda: self.browser._command(
                "click",
                **click_params(
                    self.selector,
                    button=button,
                    click_count=click_count,
                    new_tab=new_tab,
                ),
            )
        )

    async def fill(self, value: str) -> Self:
        """Fill this ref as a form control."""
        return await self._run(
            lambda: self.browser._command("fill", selector=self.selector, value=value)
        )

    async def type(self, text: str) -> Self:
        """Type text into this ref."""
        return await self._run(
            lambda: self.browser._command("type", selector=self.selector, text=text)
        )

    async def press(self, key: str) -> Self:
        """Focus this ref and press a key."""

        async def action() -> None:
            await self.browser._command("click", selector=self.selector)
            await self.browser.keyboard.press(key)

        return await self._run(action)

    async def hover(self) -> Self:
        """Hover this ref."""
        return await self._run(lambda: self.browser._command("hover", selector=self.selector))

    async def tap(self) -> Self:
        """Tap this ref."""
        return await self._run(lambda: self.browser._command("tap", selector=self.selector))

    async def focus(self) -> Self:
        """Focus this ref."""
        return await self._run(lambda: self.browser._command("focus", selector=self.selector))

    async def clear(self) -> Self:
        """Clear this ref as a form control."""
        return await self._run(lambda: self.browser._command("clear", selector=self.selector))

    async def select(self, value: str) -> Self:
        """Select an option value on this ref."""
        return await self._run(
            lambda: self.browser._command("select", selector=self.selector, value=value)
        )

    async def check(self) -> Self:
        """Check this ref."""
        return await self._run(lambda: self.browser._command("check", selector=self.selector))

    async def uncheck(self) -> Self:
        """Uncheck this ref."""
        return await self._run(lambda: self.browser._command("uncheck", selector=self.selector))

    async def scroll_into_view(self) -> Self:
        """Scroll this ref into view."""
        return await self._run(
            lambda: self.browser._command("scrollintoview", selector=self.selector)
        )

    async def wait(
        self,
        *,
        state: WaitSelectorState = "visible",
        timeout_ms: int | None = None,
    ) -> Self:
        """Wait for this ref to reach a state."""
        return await self._run(
            lambda: self.browser._command(
                "wait",
                **wait_params(
                    None,
                    selector=self.selector,
                    state=state,
                    timeout_ms=timeout_ms,
                ),
            )
        )

    async def text(self) -> str:
        """Return text content for this ref."""
        return str((await self.browser._command("gettext", selector=self.selector)).get("text", ""))

    async def inner_text(self) -> str:
        """Return rendered inner text for this ref."""
        return str(
            (await self.browser._command("innertext", selector=self.selector)).get("text", "")
        )

    async def input_value(self) -> str:
        """Return this ref's input value."""
        return str(
            (await self.browser._command("inputvalue", selector=self.selector)).get("value", "")
        )

    async def attribute(self, name: str) -> str | None:
        """Return one attribute on this ref."""
        value = (
            await self.browser._command("getattribute", selector=self.selector, attribute=name)
        ).get("value")
        return str(value) if value is not None else None

    async def is_visible(self) -> bool:
        """Return whether this ref is visible."""
        return bool(
            (await self.browser._command("isvisible", selector=self.selector)).get("visible")
        )

    async def is_enabled(self) -> bool:
        """Return whether this ref is enabled."""
        return bool(
            (await self.browser._command("isenabled", selector=self.selector)).get("enabled")
        )

    async def is_checked(self) -> bool:
        """Return whether this ref is checked."""
        return bool(
            (await self.browser._command("ischecked", selector=self.selector)).get("checked")
        )

    async def click_and_observe(
        self,
        *,
        button: MouseButton = "left",
        click_count: int = 1,
        new_tab: bool = False,
        wait_for_text: str | None = None,
        wait_for_url: str | None = None,
        wait_for_load_state: LoadState | None = None,
        compact: bool = True,
    ) -> ActionEvidence:
        """Click this ref and return before/after snapshot evidence."""
        await self.click(button=button, click_count=click_count, new_tab=new_tab)
        await self._wait_after_action(
            text=wait_for_text,
            url=wait_for_url,
            load_state=wait_for_load_state,
        )
        return await self._evidence("click", compact=compact)

    async def fill_and_observe(
        self,
        value: str,
        *,
        wait_for_text: str | None = None,
        wait_for_url: str | None = None,
        wait_for_load_state: LoadState | None = None,
        compact: bool = True,
    ) -> ActionEvidence:
        """Fill this ref and return before/after snapshot evidence."""
        await self.fill(value)
        await self._wait_after_action(
            text=wait_for_text,
            url=wait_for_url,
            load_state=wait_for_load_state,
        )
        return await self._evidence("fill", compact=compact)

    async def _wait_after_action(
        self,
        *,
        text: str | None,
        url: str | None,
        load_state: LoadState | None,
    ) -> None:
        if text is not None:
            await self.browser.page.wait_for_text(text)
        if url is not None:
            await self.browser.page.wait_for_url(url)
        if load_state is not None:
            await self.browser.page.wait_for_load_state(load_state)

    async def _evidence(self, action: str, *, compact: bool) -> ActionEvidence:
        before_snapshot = self.snapshot or await self.browser.snapshot(interactive=True)
        before = AsyncAgentSnapshot(self.browser, before_snapshot)
        after = await self.browser.observe(compact=compact)
        diff = await self.browser.diff_snapshot(before_snapshot, compact=compact)
        return ActionEvidence(
            action=action, target=self.selector, before=before, after=after, diff=diff
        )

    async def _run(self, action: Any) -> Self:
        try:
            await action()
        except BrowserError as err:
            if _is_stale_ref_error(err):
                raise AsyncStaleAgentRefError(self, err) from err
            raise
        return self


@dataclass(frozen=True, slots=True)
class AsyncAgentSnapshot:
    """Async accessibility snapshot bound to a browser."""

    browser: Any
    snapshot: Snapshot

    @property
    def text(self) -> str:
        """Snapshot text."""
        return self.snapshot.text

    @property
    def origin(self) -> str:
        """Snapshot origin URL."""
        return self.snapshot.origin

    @property
    def raw(self) -> Mapping[str, Any]:
        """Raw snapshot response."""
        return self.snapshot.raw

    @property
    def refs(self) -> Mapping[str, Mapping[str, Any]]:
        """Raw snapshot ref metadata by ref id."""
        return self.snapshot.refs

    def ref(self, ref_id: str) -> AsyncAgentRef:
        """Return one bound ref by id, accepting both `r1` and `@r1`."""
        return AsyncAgentRef(self.browser, self.snapshot.ref(ref_id), snapshot=self.snapshot)

    def find(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
        strict: bool = True,
    ) -> AsyncAgentRef:
        """Return one ref matching role/name/text criteria."""
        matches = self.find_all(role=role, name=name, contains=contains, exact=exact)
        if not matches:
            raise LookupError("snapshot contains no ref matching the requested criteria")
        if strict and len(matches) > 1:
            refs = ", ".join(match.selector for match in matches)
            raise LookupError(f"snapshot criteria matched multiple refs: {refs}")
        return matches[0]

    def find_all(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> list[AsyncAgentRef]:
        """Return all refs matching role/name/text criteria."""
        return [
            AsyncAgentRef(
                self.browser,
                snapshot_ref,
                snapshot=self.snapshot,
            )
            for snapshot_ref in self.snapshot.find_refs(
                role=role,
                name=name,
                contains=contains,
                exact=exact,
            )
        ]


@dataclass(frozen=True, slots=True)
class AsyncAgent:
    """Async agent-oriented browser operations built around snapshots and refs."""

    browser: Any

    async def observe(
        self,
        *,
        selector: str | None = None,
        interactive: bool = True,
        compact: bool = False,
        max_depth: int | None = None,
        urls: bool = False,
    ) -> AsyncAgentSnapshot:
        """Capture a snapshot and bind it to this browser."""
        return AsyncAgentSnapshot(
            self.browser,
            await self.browser.snapshot(
                selector=selector,
                interactive=interactive,
                compact=compact,
                max_depth=max_depth,
                urls=urls,
            ),
        )

    def ref(self, ref_id: str) -> AsyncLocator:
        """Return an async locator for a snapshot ref id such as `r1` or `@r1`."""
        return AsyncLocator(self.browser, ref_selector(ref_id))


def _is_stale_ref_error(error: BrowserError) -> bool:
    return is_stale_ref_error_code(error.code)
