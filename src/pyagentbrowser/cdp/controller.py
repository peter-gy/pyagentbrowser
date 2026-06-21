from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pyagentbrowser.cdp._resolution import _resolve_active_target
from pyagentbrowser.cdp.client import AsyncCDPClient, CDPClient
from pyagentbrowser.cdp.errors import CDPError
from pyagentbrowser.cdp.models import (
    AsyncContextPredicate,
    AsyncExecutionContext,
    AsyncFrame,
    ContextPredicate,
    ExecutionContext,
    Frame,
)
from pyagentbrowser.cdp.page import AsyncCDPPageSession, CDPPageSession
from pyagentbrowser.cdp.target import AsyncCDPTarget, CDPTarget


class CDPController:
    """High-level synchronous CDP controller for one browser.

    The controller keeps one CDP client and one active page session. Native
    navigation invalidates the page session so cached `Frame` and
    `ExecutionContext` handles can fail fast instead of evaluating against stale
    targets.
    """

    def __init__(self, browser: Any, *, client_factory: Callable[[str], CDPClient] | None = None):
        self._browser = browser
        self._client_factory = client_factory or CDPClient
        self._client: CDPClient | None = None
        self._page: CDPPageSession | None = None

    def frame(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> Frame:
        """Return one frame selected by iframe selector, name, or URL."""
        return self._page_session().frame(selector=selector, name=name, url=url)

    def target(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> CDPTarget:
        """Return a handle for a selected CDP target."""
        return CDPTarget(self, label=label, url=url, target_id=target_id)

    def frames(self) -> list[Frame]:
        """Return frames for the active page target."""
        return self._page_session().frames()

    def contexts(
        self,
        *,
        frame: str | Frame | None = None,
        extension_id: str | None = None,
        predicate: ContextPredicate | None = None,
    ) -> list[ExecutionContext]:
        """Return execution contexts matching optional frame and extension filters."""
        page = self._page_session()
        return page.contexts(
            frame=page.resolve_frame(frame),
            extension_id=extension_id,
            predicate=predicate,
        )

    def evaluate(
        self,
        script: str,
        *,
        frame: str | Frame | None = None,
        extension_id: str | None = None,
        context: ExecutionContext | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in a selected frame or execution context."""
        page = self._page_session()
        if context is not None:
            return page.evaluate(
                script,
                context=context,
                await_promise=await_promise,
                return_by_value=return_by_value,
            )
        return page.evaluate(
            script,
            frame=page.resolve_frame(frame),
            extension_id=extension_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    def invalidate(self) -> None:
        """Forget cached CDP page state after navigation-like native commands."""
        if self._page is not None:
            self._page.invalidate()
            self._page = None

    def close(self) -> None:
        """Close the CDP client and forget page state."""
        if self._client is not None:
            self._client.close()
            self._client = None
        self._page = None

    def _page_session(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> CDPPageSession:
        if self._page is not None and label is None and url is None and target_id is None:
            return self._page

        client = self._cdp_client()
        if target_id is None and url is None and label is not None:
            target_id = self._target_id_for_tab_label(label)
        target = _resolve_active_target(
            client.send("Target.getTargets"),
            self._browser.page.url(),
            label=None if target_id is not None else label,
            url=url,
            target_id=target_id,
        )
        target_id = str(target["targetId"])
        if self._page is not None and self._page.target_id == target_id:
            return self._page
        attached = client.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        session_id = str(attached["sessionId"])
        self._page = CDPPageSession(client, session_id=session_id, target_id=target_id)
        self._page.enable()
        return self._page

    def _cdp_client(self) -> CDPClient:
        if self._client is not None:
            return self._client
        if not self._browser.is_launched:
            self._browser.launch()
        cdp_url = self._browser.command("cdp_url").get("cdpUrl")
        if not isinstance(cdp_url, str) or not cdp_url:
            raise CDPError('browser.command("cdp_url") did not return a cdpUrl string')
        self._client = self._client_factory(cdp_url)
        return self._client

    def _target_id_for_tab_label(self, label: str) -> str | None:
        for tab in self._browser.tabs.list():
            if getattr(tab, "label", None) != label:
                continue
            raw = getattr(tab, "raw", {})
            if isinstance(raw, Mapping):
                target_id = raw.get("targetId")
                if isinstance(target_id, str) and target_id:
                    return target_id
            return None
        return None


class AsyncCDPController:
    """High-level async CDP controller for one browser.

    The controller keeps one CDP client and one active page session. Native
    navigation invalidates the page session so cached `AsyncFrame` and
    `AsyncExecutionContext` handles can fail fast instead of evaluating against
    stale targets.
    """

    def __init__(
        self,
        browser: Any,
        *,
        client_factory: Callable[[str], AsyncCDPClient] | None = None,
    ):
        self._browser = browser
        self._client_factory = client_factory or AsyncCDPClient
        self._client: AsyncCDPClient | None = None
        self._page: AsyncCDPPageSession | None = None

    async def frame(
        self,
        *,
        selector: str | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> AsyncFrame:
        """Return one frame selected by iframe selector, name, or URL."""
        return await (await self._page_session()).frame(selector=selector, name=name, url=url)

    def target(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> AsyncCDPTarget:
        """Return a handle for a selected CDP target."""
        return AsyncCDPTarget(self, label=label, url=url, target_id=target_id)

    async def frames(self) -> list[AsyncFrame]:
        """Return frames for the active page target."""
        return await (await self._page_session()).frames()

    async def contexts(
        self,
        *,
        frame: str | AsyncFrame | None = None,
        extension_id: str | None = None,
        predicate: AsyncContextPredicate | None = None,
    ) -> list[AsyncExecutionContext]:
        """Return execution contexts matching optional frame and extension filters."""
        page = await self._page_session()
        return await page.contexts(
            frame=await page.resolve_frame(frame),
            extension_id=extension_id,
            predicate=predicate,
        )

    async def evaluate(
        self,
        script: str,
        *,
        frame: str | AsyncFrame | None = None,
        extension_id: str | None = None,
        context: AsyncExecutionContext | None = None,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate JavaScript in a selected frame or execution context."""
        page = await self._page_session()
        if context is not None:
            return await page.evaluate(
                script,
                context=context,
                await_promise=await_promise,
                return_by_value=return_by_value,
            )
        return await page.evaluate(
            script,
            frame=await page.resolve_frame(frame),
            extension_id=extension_id,
            await_promise=await_promise,
            return_by_value=return_by_value,
        )

    def invalidate(self) -> None:
        """Forget cached CDP page state after navigation-like native commands."""
        if self._page is not None:
            self._page.invalidate()
            self._page = None

    async def close(self) -> None:
        """Close the CDP client and forget page state."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._page = None

    async def _page_session(
        self,
        *,
        label: str | None = None,
        url: str | None = None,
        target_id: str | None = None,
    ) -> AsyncCDPPageSession:
        if self._page is not None and label is None and url is None and target_id is None:
            return self._page

        client = await self._cdp_client()
        if target_id is None and url is None and label is not None:
            target_id = await self._target_id_for_tab_label(label)
        target = _resolve_active_target(
            await client.send("Target.getTargets"),
            await self._browser.page.url(),
            label=None if target_id is not None else label,
            url=url,
            target_id=target_id,
        )
        target_id = str(target["targetId"])
        if self._page is not None and self._page.target_id == target_id:
            return self._page
        attached = await client.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        session_id = str(attached["sessionId"])
        self._page = AsyncCDPPageSession(client, session_id=session_id, target_id=target_id)
        await self._page.enable()
        return self._page

    async def _cdp_client(self) -> AsyncCDPClient:
        if self._client is not None:
            return self._client
        if not self._browser.is_launched:
            await self._browser.launch()
        cdp_url = (await self._browser.command("cdp_url")).get("cdpUrl")
        if not isinstance(cdp_url, str) or not cdp_url:
            raise CDPError('browser.command("cdp_url") did not return a cdpUrl string')
        self._client = self._client_factory(cdp_url)
        return self._client

    async def _target_id_for_tab_label(self, label: str) -> str | None:
        for tab in await self._browser.tabs.list():
            if getattr(tab, "label", None) != label:
                continue
            raw = getattr(tab, "raw", {})
            if isinstance(raw, Mapping):
                target_id = raw.get("targetId")
                if isinstance(target_id, str) and target_id:
                    return target_id
            return None
        return None
