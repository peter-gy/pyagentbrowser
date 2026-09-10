from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Self, TypeVar

from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.contracts.protocol import optional
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Queries:
    """Factory for live selector and semantic queries."""

    executor: Executor

    def css(self, selector: str) -> Query:
        """Create a live CSS query."""
        if not selector:
            raise ValueError("selector must not be empty")
        return Query(self.executor, selector=selector)

    def xpath(self, expression: str) -> Query:
        """Create a live XPath query."""
        expression = expression.removeprefix("xpath=")
        if not expression:
            raise ValueError("expression must not be empty")
        return Query(self.executor, selector=f"xpath={expression}")

    def role(self, role: str, *, name: str | None = None, exact: bool = False) -> Query:
        """Create a live accessible-role query."""
        return Query(
            self.executor,
            action="getbyrole",
            params={"role": role, "name": optional(name), "exact": exact},
        )

    def text(self, text: str, *, exact: bool = False) -> Query:
        """Create a live visible-text query."""
        return Query(
            self.executor,
            action="getbytext",
            params={"text": text, "exact": exact},
        )

    def label(self, label: str, *, exact: bool = False) -> Query:
        """Create a live form-label query."""
        return Query(
            self.executor,
            action="getbylabel",
            params={"label": label, "exact": exact},
        )

    def placeholder(self, placeholder: str, *, exact: bool = False) -> Query:
        """Create a live placeholder query."""
        return Query(
            self.executor,
            action="getbyplaceholder",
            params={"placeholder": placeholder, "exact": exact},
        )

    def alt_text(self, text: str, *, exact: bool = False) -> Query:
        """Create a live image-alt query."""
        return Query(
            self.executor,
            action="getbyalttext",
            params={"text": text, "exact": exact},
        )

    def title(self, text: str, *, exact: bool = False) -> Query:
        """Create a live title-attribute query."""
        return Query(
            self.executor,
            action="getbytitle",
            params={"text": text, "exact": exact},
        )

    def test_id(self, test_id: str) -> Query:
        """Create a live test-id query."""
        return Query(
            self.executor,
            action="getbytestid",
            params={"testId": test_id},
        )


@dataclass(frozen=True, slots=True)
class Query:
    """Live element query resolved by the native engine at action time."""

    executor: Executor
    selector: str | None = None
    action: str | None = None
    params: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if (self.selector is None) == (self.action is None):
            raise ValueError("query requires exactly one of selector or action")
        if self.selector is not None and not self.selector:
            raise ValueError("selector must not be empty")
        if self.action is not None and not self.action:
            raise ValueError("action must not be empty")
        if self.selector is not None and self.params is not None:
            raise ValueError("params require an action query")
        if self.executor is None:
            raise TypeError("query requires a browser")

    def click(self) -> Self:
        """Click the current match."""
        return self._act("click", decode=lambda _data: self)

    def fill(self, value: str) -> Self:
        """Fill the current match."""
        return self._act("fill", decode=lambda _data: self, value=value)

    def check(self) -> Self:
        """Check the current match."""
        return self._act("check", decode=lambda _data: self)

    def hover(self) -> Self:
        """Hover the current match."""
        return self._act("hover", decode=lambda _data: self)

    def text(self) -> str:
        """Return text for the current match."""
        return self._act("text", decode=_text)

    def _act(
        self,
        subaction: str,
        *,
        decode: Callable[[Mapping[str, Any]], T],
        **params: Any,
    ) -> T:
        if self.selector is not None:
            action = {
                "click": "click",
                "fill": "fill",
                "check": "check",
                "hover": "hover",
                "text": "gettext",
            }[subaction]
            return self.executor.execute(
                Command(action, {"selector": self.selector, **params}, decode=decode)
            )
        action = self.action
        if action is None:
            raise RuntimeError("query has no native action")
        return self.executor.execute(
            Command(
                action, {**dict(self.params or {}), "subaction": subaction, **params}, decode=decode
            )
        )


def _text(data: Mapping[str, Any]) -> str:
    value = data.get("text")
    if not isinstance(value, str):
        raise NativeParseError("query text field 'text' must be a string")
    return value


@dataclass(frozen=True, slots=True)
class AsyncQueries:
    """Factory for async live selector and semantic queries."""

    executor: AsyncExecutor

    def css(self, selector: str) -> AsyncQuery:
        """Create a live CSS query."""
        if not selector:
            raise ValueError("selector must not be empty")
        return AsyncQuery(self.executor, selector=selector)

    def xpath(self, expression: str) -> AsyncQuery:
        """Create a live XPath query."""
        expression = expression.removeprefix("xpath=")
        if not expression:
            raise ValueError("expression must not be empty")
        return AsyncQuery(self.executor, selector=f"xpath={expression}")

    def role(
        self,
        role: str,
        *,
        name: str | None = None,
        exact: bool = False,
    ) -> AsyncQuery:
        """Create a live accessible-role query."""
        return AsyncQuery(
            self.executor,
            action="getbyrole",
            params={"role": role, "name": optional(name), "exact": exact},
        )

    def text(self, text: str, *, exact: bool = False) -> AsyncQuery:
        """Create a live visible-text query."""
        return AsyncQuery(
            self.executor,
            action="getbytext",
            params={"text": text, "exact": exact},
        )

    def label(self, label: str, *, exact: bool = False) -> AsyncQuery:
        """Create a live form-label query."""
        return AsyncQuery(
            self.executor,
            action="getbylabel",
            params={"label": label, "exact": exact},
        )

    def placeholder(self, placeholder: str, *, exact: bool = False) -> AsyncQuery:
        """Create a live placeholder query."""
        return AsyncQuery(
            self.executor,
            action="getbyplaceholder",
            params={"placeholder": placeholder, "exact": exact},
        )

    def alt_text(self, text: str, *, exact: bool = False) -> AsyncQuery:
        """Create a live image-alt query."""
        return AsyncQuery(
            self.executor,
            action="getbyalttext",
            params={"text": text, "exact": exact},
        )

    def title(self, text: str, *, exact: bool = False) -> AsyncQuery:
        """Create a live title-attribute query."""
        return AsyncQuery(
            self.executor,
            action="getbytitle",
            params={"text": text, "exact": exact},
        )

    def test_id(self, test_id: str) -> AsyncQuery:
        """Create a live test-id query."""
        return AsyncQuery(
            self.executor,
            action="getbytestid",
            params={"testId": test_id},
        )


@dataclass(frozen=True, slots=True)
class AsyncQuery:
    """Live async query resolved by the native engine at action time."""

    executor: AsyncExecutor
    selector: str | None = None
    action: str | None = None
    params: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if (self.selector is None) == (self.action is None):
            raise ValueError("query requires exactly one of selector or action")
        if self.selector is not None and not self.selector:
            raise ValueError("selector must not be empty")
        if self.action is not None and not self.action:
            raise ValueError("action must not be empty")
        if self.selector is not None and self.params is not None:
            raise ValueError("params require an action query")
        if self.executor is None:
            raise TypeError("query requires a browser")

    async def click(self) -> Self:
        """Click the current match."""
        return await self._act("click", decode=lambda _data: self)

    async def fill(self, value: str) -> Self:
        """Fill the current match."""
        return await self._act("fill", decode=lambda _data: self, value=value)

    async def check(self) -> Self:
        """Check the current match."""
        return await self._act("check", decode=lambda _data: self)

    async def hover(self) -> Self:
        """Hover the current match."""
        return await self._act("hover", decode=lambda _data: self)

    async def text(self) -> str:
        """Return text for the current match."""
        return await self._act("text", decode=_text)

    async def _act(
        self,
        subaction: str,
        *,
        decode: Callable[[Mapping[str, Any]], T],
        **params: Any,
    ) -> T:
        if self.selector is not None:
            action = {
                "click": "click",
                "fill": "fill",
                "check": "check",
                "hover": "hover",
                "text": "gettext",
            }[subaction]
            return await self.executor.execute(
                Command(action, {"selector": self.selector, **params}, decode=decode)
            )
        action = self.action
        if action is None:
            raise RuntimeError("query has no native action")
        return await self.executor.execute(
            Command(
                action, {**dict(self.params or {}), "subaction": subaction, **params}, decode=decode
            )
        )
