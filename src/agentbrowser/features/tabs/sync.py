from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from agentbrowser.contracts.connection import normalize_url
from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.contracts.protocol import optional
from agentbrowser.execution.commands import Command, Executor
from agentbrowser.features.documents.handles import Page
from agentbrowser.features.documents.models import LoadState
from agentbrowser.features.tabs.codec import (
    tab_close_result_from_data,
    tab_from_data,
    tab_switch_from_data,
    tabs_from_data,
)
from agentbrowser.features.tabs.models import TabCloseResult, TabInfo, TabSwitchResult
from agentbrowser.features.tabs.shared import _tab_selector, _tab_with_label


@dataclass(frozen=True, slots=True)
class Tabs:
    """Tab listing, creation, switching, and closing helpers."""

    executor: Executor

    def list(self) -> tuple[TabInfo, ...]:
        """Return open tabs."""
        return self.executor.execute(Command("tab_list", {}, decode=tabs_from_data))

    def get(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> Page:
        """Return a page handle bound to one exact browser target."""
        selected = [value is not None for value in (id, label, index)]
        if sum(selected) != 1:
            raise ValueError("pass exactly one of id, label, or index")
        if index is not None and index < 1:
            raise ValueError("index must be a positive stable tab ID suffix")
        try:
            tabs = self.list()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda tabs: self._get_from_tabs(tabs, id=id, label=label, index=index)
                )
            raise
        return self._get_from_tabs(tabs, id=id, label=label, index=index)

    def _get_from_tabs(
        self,
        tabs: Sequence[TabInfo],
        *,
        id: str | None,
        label: str | None,
        index: int | None,
    ) -> Page:
        if index is not None:
            matches = [tab for tab in tabs if tab.id == f"t{index}"]
        elif label is not None:
            matches = [tab for tab in tabs if tab.label == label]
        else:
            matches = [tab for tab in tabs if id in {tab.id, tab.target_id}]
        if not matches:
            raise LookupError("no browser page matched the requested tab")
        if len(matches) > 1:
            raise LookupError("multiple browser pages matched the requested tab")
        tab = matches[0]
        target_id = tab.target_id or tab.id
        return Page(self.executor, target_id=target_id, frame_url=tab.url)

    def new(self, url: str | None = None, *, label: str | None = None) -> TabInfo:
        """Open a new tab and return its metadata."""
        return self.executor.execute(
            Command(
                "tab_new", {"url": optional(url), "label": optional(label)}, decode=tab_from_data
            )
        )

    def open(
        self,
        url: str,
        *,
        label: str | None = None,
        reuse: bool = True,
        wait_until: LoadState = "load",
    ) -> TabInfo:
        """Open a URL in a tab, reusing a labelled tab when available."""
        normalized_url = normalize_url(url)
        if label is None or not reuse:
            return self.new(normalized_url, label=label)

        try:
            tabs = self.list()
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda confirmed: self._open_from_tabs(
                        normalized_url,
                        label,
                        confirmed,
                        wait_until,
                    )
                )
            raise
        return self._open_from_tabs(normalized_url, label, tabs, wait_until)

    def _open_from_tabs(
        self,
        normalized_url: str,
        label: str,
        tabs: Sequence[TabInfo],
        wait_until: LoadState,
    ) -> TabInfo:
        existing = _tab_with_label(tabs, label)
        if existing is None:
            return self.new(normalized_url, label=label)

        try:
            self.switch(id=existing.id)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(
                    lambda _value: self._navigate_reused(
                        existing,
                        normalized_url,
                        wait_until,
                    )
                )
            raise
        return self._navigate_reused(existing, normalized_url, wait_until)

    def _navigate_reused(
        self,
        existing: TabInfo,
        normalized_url: str,
        wait_until: LoadState,
    ) -> TabInfo:
        return self.executor.execute(
            Command(
                "navigate",
                {"url": normalized_url, "waitUntil": wait_until},
                decode=lambda _data: replace(existing, url=normalized_url, active=True),
            )
        )

    def switch(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> TabSwitchResult:
        """Switch to a tab and return observed renderer state."""
        return self.executor.execute(
            Command(
                "tab_switch",
                {"tabId": self._resolve_selector(id=id, label=label, index=index, required=True)},
                decode=tab_switch_from_data,
            )
        )

    def close(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
    ) -> TabCloseResult:
        """Close a tab and return observed successor reactivation."""
        return self.executor.execute(
            Command(
                "tab_close",
                {"tabId": self._resolve_selector(id=id, label=label, index=index)},
                decode=tab_close_result_from_data,
            )
        )

    def _resolve_selector(
        self,
        *,
        id: str | None = None,
        label: str | None = None,
        index: int | None = None,
        required: bool = False,
    ) -> str | Any:
        selected = [value is not None for value in (id, label, index)]
        if sum(selected) == 0:
            if required:
                raise ValueError("pass one of id, label, or index")
            return optional(None)
        if sum(selected) > 1:
            raise ValueError("pass exactly one of id, label, or index")
        if label is not None:
            return label
        return _tab_selector(id=id, index=index, required=required)
