from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agentbrowser.contracts.actions import (
    CDP_URL_ACTIONS,
    action_clears_pending_confirmation,
    action_closes_browser,
    action_invalidates_cdp,
    action_resets_cdp,
    action_sets_launched,
    response_browser_launched,
)
from agentbrowser.contracts.protocol import BrowserResponse


@dataclass
class CommandState:
    pending_invalidations: set[str] = field(default_factory=set)
    generation: int = 0
    target_id: str | None = None
    launched: bool = False

    def invalidation_context(
        self,
        action: str,
        params: Mapping[str, Any],
    ) -> tuple[str | None, bool]:
        confirmation_value = (
            params.get("confirmation_id") if action in {"confirm", "deny"} else None
        )
        pending_id = str(confirmation_value) if confirmation_value is not None else None
        # URL commands can fail after navigation. Preserve invalidation across
        # confirmation because the confirmed response omits the URL.
        compound_invalidation = action in CDP_URL_ACTIONS and action_invalidates_cdp(action, params)
        if action == "confirm" and pending_id in self.pending_invalidations:
            compound_invalidation = True
        return pending_id, compound_invalidation

    def continue_invalidation(
        self,
        previous_id: str | None,
        next_id: str | None,
        enabled: bool,
    ) -> None:
        if previous_id is not None:
            self.pending_invalidations.discard(previous_id)
        if enabled and next_id is not None:
            self.pending_invalidations.add(next_id)

    def record_metadata(self, response: BrowserResponse) -> bool:
        generation = response.raw.get("refGeneration")
        if isinstance(generation, int):
            self.generation = generation
        target_id = response.raw.get("targetId")
        if isinstance(target_id, str):
            self.target_id = target_id
            self.launched = True
        return bool(response.raw.get("scopeSwitched"))

    def record_success(
        self,
        response: BrowserResponse,
        *,
        params: Mapping[str, Any] | None = None,
        force_cdp_invalidation: bool = False,
    ) -> Literal["reset", "invalidate"] | None:
        action = response.action
        if response.raw.get("refGeneration") is None and (
            action in {"snapshot", "diff_snapshot", "diff_url"}
            or (action == "screenshot" and bool((params or {}).get("annotate")))
        ):
            self.generation += 1
        browser_launched = response_browser_launched(response)
        if browser_launched is not None:
            self.launched = browser_launched
        elif action_sets_launched(action):
            self.launched = True
        elif action_clears_pending_confirmation(action) and action_closes_browser(action):
            self.launched = False
        if action_closes_browser(action):
            self.pending_invalidations.clear()
        if action_resets_cdp(action):
            return "reset"
        if force_cdp_invalidation or action_invalidates_cdp(action, params):
            return "invalidate"
        return None
