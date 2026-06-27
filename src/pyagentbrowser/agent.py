from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from typing_extensions import Self

from pyagentbrowser._browser_common import is_stale_ref_error_code
from pyagentbrowser.command_params import click_params, wait_params
from pyagentbrowser.domains import Locator
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


class StaleAgentRefError(BrowserError):
    """Raised when an action targets a stale snapshot ref.

    Parameters
    ----------
    ref
        Bound snapshot ref that failed.
    error
        Native browser error raised by the attempted action.
    """

    def __init__(self, ref: AgentRef, error: BrowserError) -> None:
        super().__init__(
            error.action, f"stale snapshot ref {ref.selector}: {error}", error.response
        )
        self.ref = ref

    def refresh(self, **criteria: Any) -> AgentRef:
        """Refresh the stale ref using optional match criteria."""
        return self.ref.refresh(**criteria)


@dataclass(frozen=True, slots=True)
class AgentRef:
    """Bound snapshot ref with direct element actions.

    `AgentRef` is returned by `AgentSnapshot.ref()`, `find()`, and `find_all()`.
    It keeps the snapshot selector, role, name, and browser needed to perform
    direct element actions.
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

    def locator(self) -> Locator:
        """Return a lower-level locator for this snapshot ref."""
        return Locator(self.browser, self.selector)

    def refresh(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = True,
        strict: bool = True,
    ) -> AgentRef:
        """Re-find this ref in a fresh snapshot.

        Parameters
        ----------
        role, name, contains, exact, strict
            Match criteria forwarded to `AgentSnapshot.find()`.

        Returns
        -------
        AgentRef
            Freshly resolved bound ref.
        """
        return self.browser.agent.observe().find(
            role=self.role if role is None else role,
            name=self.name if name is None and contains is None else name,
            contains=contains,
            exact=exact,
            strict=strict,
        )

    def click(
        self,
        *,
        button: MouseButton = "left",
        click_count: int = 1,
        new_tab: bool = False,
    ) -> Self:
        """Click this ref and return it."""
        return self._run(
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

    def fill(self, value: str) -> Self:
        """Fill this ref as a form control."""
        return self._run(lambda: self.browser._command("fill", selector=self.selector, value=value))

    def type(self, text: str) -> Self:
        """Type text into this ref."""
        return self._run(lambda: self.browser._command("type", selector=self.selector, text=text))

    def press(self, key: str) -> Self:
        """Focus this ref and press a key."""
        return self._run(
            lambda: (
                self.browser._command("click", selector=self.selector),
                self.browser.keyboard.press(key),
            )
        )

    def hover(self) -> Self:
        """Hover this ref."""
        return self._run(lambda: self.browser._command("hover", selector=self.selector))

    def tap(self) -> Self:
        """Tap this ref."""
        return self._run(lambda: self.browser._command("tap", selector=self.selector))

    def focus(self) -> Self:
        """Focus this ref."""
        return self._run(lambda: self.browser._command("focus", selector=self.selector))

    def clear(self) -> Self:
        """Clear this ref as a form control."""
        return self._run(lambda: self.browser._command("clear", selector=self.selector))

    def select(self, value: str) -> Self:
        """Select an option value on this ref."""
        return self._run(
            lambda: self.browser._command("select", selector=self.selector, value=value)
        )

    def check(self) -> Self:
        """Check this ref."""
        return self._run(lambda: self.browser._command("check", selector=self.selector))

    def uncheck(self) -> Self:
        """Uncheck this ref."""
        return self._run(lambda: self.browser._command("uncheck", selector=self.selector))

    def scroll_into_view(self) -> Self:
        """Scroll this ref into view."""
        return self._run(lambda: self.browser._command("scrollintoview", selector=self.selector))

    def wait(self, *, state: WaitSelectorState = "visible", timeout_ms: int | None = None) -> Self:
        """Wait for this ref to reach a state."""
        return self._run(
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

    def text(self) -> str:
        """Return text content for this ref."""
        return str(self.browser._command("gettext", selector=self.selector).get("text", ""))

    def inner_text(self) -> str:
        """Return rendered inner text for this ref."""
        return str(self.browser._command("innertext", selector=self.selector).get("text", ""))

    def input_value(self) -> str:
        """Return this ref's input value."""
        return str(self.browser._command("inputvalue", selector=self.selector).get("value", ""))

    def attribute(self, name: str) -> str | None:
        """Return one attribute on this ref."""
        value = self.browser._command("getattribute", selector=self.selector, attribute=name).get(
            "value"
        )
        return str(value) if value is not None else None

    def is_visible(self) -> bool:
        """Return whether this ref is visible."""
        return bool(self.browser._command("isvisible", selector=self.selector).get("visible"))

    def is_enabled(self) -> bool:
        """Return whether this ref is enabled."""
        return bool(self.browser._command("isenabled", selector=self.selector).get("enabled"))

    def is_checked(self) -> bool:
        """Return whether this ref is checked."""
        return bool(self.browser._command("ischecked", selector=self.selector).get("checked"))

    def click_and_observe(
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
        self.click(button=button, click_count=click_count, new_tab=new_tab)
        self._wait_after_action(
            text=wait_for_text,
            url=wait_for_url,
            load_state=wait_for_load_state,
        )
        return self._evidence("click", compact=compact)

    def fill_and_observe(
        self,
        value: str,
        *,
        wait_for_text: str | None = None,
        wait_for_url: str | None = None,
        wait_for_load_state: LoadState | None = None,
        compact: bool = True,
    ) -> ActionEvidence:
        """Fill this ref and return before/after snapshot evidence."""
        self.fill(value)
        self._wait_after_action(
            text=wait_for_text,
            url=wait_for_url,
            load_state=wait_for_load_state,
        )
        return self._evidence("fill", compact=compact)

    def _wait_after_action(
        self,
        *,
        text: str | None,
        url: str | None,
        load_state: LoadState | None,
    ) -> None:
        if text is not None:
            self.browser.page.wait_for_text(text)
        if url is not None:
            self.browser.page.wait_for_url(url)
        if load_state is not None:
            self.browser.page.wait_for_load_state(load_state)

    def _evidence(self, action: str, *, compact: bool) -> ActionEvidence:
        before_snapshot = self.snapshot or self.browser.snapshot(interactive=True)
        before = AgentSnapshot(self.browser, before_snapshot)
        after = self.browser.observe(compact=compact)
        diff = self.browser.diff_snapshot(before_snapshot, compact=compact)
        return ActionEvidence(
            action=action, target=self.selector, before=before, after=after, diff=diff
        )

    def _run(self, action: Any) -> Self:
        try:
            action()
        except BrowserError as err:
            if _is_stale_ref_error(err):
                raise StaleAgentRefError(self, err) from err
            raise
        return self


@dataclass(frozen=True, slots=True)
class AgentSnapshot:
    """Accessibility snapshot bound to a browser.

    The wrapper exposes raw snapshot text and turns snapshot refs into
    `AgentRef` objects that can be clicked, filled, queried, or refreshed.
    """

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

    def ref(self, ref_id: str) -> AgentRef:
        """Return one bound ref by id, accepting both `r1` and `@r1`."""
        return AgentRef(self.browser, self.snapshot.ref(ref_id), snapshot=self.snapshot)

    def find(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
        strict: bool = True,
    ) -> AgentRef:
        """Return one ref matching role/name/text criteria.

        Parameters
        ----------
        role
            Accessible role to match.
        name
            Accessible name to match.
        contains
            Substring that must appear in the accessible name.
        exact
            Whether `name` or `contains` matching is exact.
        strict
            Raise if multiple refs match.
        """
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
    ) -> list[AgentRef]:
        """Return all refs matching role/name/text criteria."""
        return [
            AgentRef(
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
class Agent:
    """Agent-oriented browser operations built around snapshots and refs."""

    browser: Any

    def observe(
        self,
        *,
        selector: str | None = None,
        interactive: bool = True,
        compact: bool = False,
        max_depth: int | None = None,
        urls: bool = False,
    ) -> AgentSnapshot:
        """Capture a snapshot and bind it to this browser.

        Returns
        -------
        AgentSnapshot
            Snapshot wrapper whose refs can be acted on directly.
        """
        return AgentSnapshot(
            self.browser,
            self.browser.snapshot(
                selector=selector,
                interactive=interactive,
                compact=compact,
                max_depth=max_depth,
                urls=urls,
            ),
        )

    def ref(self, ref_id: str) -> Locator:
        """Return a locator for a snapshot ref id such as `r1` or `@r1`."""
        return Locator(self.browser, ref_selector(ref_id))


def _is_stale_ref_error(error: BrowserError) -> bool:
    return is_stale_ref_error_code(error.code)
