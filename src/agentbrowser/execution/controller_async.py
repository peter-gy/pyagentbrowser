from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast, overload

from agentbrowser.contracts.actions import confirmation_id, response_confirmation_id
from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.contracts.protocol import BrowserResponse, response_data_mapping
from agentbrowser.contracts.types import JSONMapping, JSONValue
from agentbrowser.execution.commands import AsyncBoundExecutor
from agentbrowser.execution.configuration import configure_session
from agentbrowser.execution.pending import AsyncPendingAction
from agentbrowser.execution.startup import Startup, requires_start
from agentbrowser.execution.state import CommandState
from agentbrowser.features.session.codec import close_result_from_data
from agentbrowser.features.session.models import CloseResult, RestoreSaveError
from agentbrowser.launch import LaunchConfiguration, LaunchOptions, SessionOptions
from agentbrowser.transport.async_ import AsyncNativeSession
from agentbrowser.transport.responses import (
    _checked_response,
    _require_response_data_mapping,
    _try_unwrap_confirmed_response,
)

if TYPE_CHECKING:
    from agentbrowser.cdp import AsyncCDPController


T = TypeVar("T")


class AsyncController:
    def __init__(
        self,
        launch_configuration: LaunchConfiguration,
        *,
        session: SessionOptions | None = None,
        native_session: AsyncNativeSession | None = None,
    ) -> None:
        self._session = configure_session(
            launch_configuration, session, native_session, AsyncNativeSession
        )
        self._startup = Startup(launch_configuration, auto_install=native_session is None)
        self._state = CommandState()
        self._cdp_controller: AsyncCDPController | None = None
        self._close_task: asyncio.Task[CloseResult] | None = None

    @property
    def _active_target_id(self) -> str | None:
        return self._state.target_id

    @property
    def _ref_generation(self) -> int:
        return self._state.generation

    @_ref_generation.setter
    def _ref_generation(self, value: int) -> None:
        self._state.generation = value

    @property
    def _launched(self) -> bool:
        return self._state.launched

    @property
    def closed(self) -> bool:
        return self._close_task is not None or self._session.closed

    async def start(self, *, options: LaunchOptions | None = None) -> JSONMapping:
        self._ensure_open()
        params = await self._startup.launch_params_async(options)
        return await self._command("launch", **params)

    def _record_native_metadata(self, response: BrowserResponse) -> None:
        if self._state.record_metadata(response):
            self._invalidate_cdp()

    async def _record_successful_action(
        self,
        response: BrowserResponse,
        *,
        params: Mapping[str, Any] | None = None,
        force_cdp_invalidation: bool = False,
    ) -> None:
        effect = self._state.record_success(
            response, params=params, force_cdp_invalidation=force_cdp_invalidation
        )
        if effect == "reset":
            await self._reset_cdp()
        elif effect == "invalidate":
            self._invalidate_cdp()

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeError("AsyncBrowser is closed")

    @overload
    async def _command(
        self,
        action: str,
        *,
        _decode: Callable[[JSONMapping], T],
        **params: Any,
    ) -> T: ...

    @overload
    async def _command(
        self,
        action: str,
        *,
        _decode: None = None,
        **params: Any,
    ) -> JSONMapping: ...

    async def _command(
        self,
        action: str,
        *,
        _decode: Callable[[JSONMapping], T] | None = None,
        **params: Any,
    ) -> T | JSONMapping:
        self._ensure_open()
        if not self._launched and requires_start(action, params):
            try:
                await self.start()
            except ConfirmationRequired as error:
                if error.pending is not None:
                    error.pending = error.pending.map(
                        lambda _value: self._command(action, _decode=_decode, **params)
                    )
                raise
        try:
            data = await self._native_data(action, expect="object", **params)
        except ConfirmationRequired as err:
            if err.confirmation_id is not None:
                err.pending = self._pending_action(err, decoder=_decode)
            raise
        mapping = cast(JSONMapping, data)
        return _decode(mapping) if _decode is not None else mapping

    async def _native_data(
        self,
        action: str,
        *,
        expect: str = "object",
        **params: Any,
    ) -> JSONMapping | JSONValue:
        self._ensure_open()
        if expect not in {"object", "any"}:
            raise ValueError('expect must be "object" or "any"')
        await self._startup.prepare_action_async(action, params, launched=self._launched)
        pending_id, compound_invalidation = self._state.invalidation_context(action, params)
        confirmation_consumed = False
        try:
            raw_response = await self._session.execute(action, **params)
            self._record_native_metadata(raw_response)
            confirmation_consumed = action == "confirm" and raw_response.success
            response = _checked_response(action, raw_response)
        except ConfirmationRequired as err:
            self._state.continue_invalidation(
                pending_id,
                err.confirmation_id,
                compound_invalidation,
            )
            if err.confirmation_id is not None:
                err.pending = self._pending_action(
                    err,
                    expect=cast(Literal["object", "any"], expect),
                )
            raise
        except BaseException:
            if compound_invalidation:
                self._invalidate_cdp()
            if pending_id is not None and confirmation_consumed:
                self._state.pending_invalidations.discard(pending_id)
            raise
        if pending_id is not None and (action == "deny" or confirmation_consumed):
            self._state.pending_invalidations.discard(pending_id)
        await self._record_successful_action(
            response,
            params=params,
            force_cdp_invalidation=compound_invalidation,
        )
        if expect == "any":
            return response.data
        return _require_response_data_mapping(response)

    async def _native_execute(self, action: str, **params: Any) -> BrowserResponse:
        self._ensure_open()
        await self._startup.prepare_action_async(action, params, launched=self._launched)
        pending_id, compound_invalidation = self._state.invalidation_context(action, params)
        try:
            response = await self._session.execute(action, **params)
            self._record_native_metadata(response)
        except BaseException:
            if compound_invalidation:
                self._invalidate_cdp()
            raise
        confirmation_consumed = action == "confirm" and response.success
        if confirmation_consumed:
            response = _try_unwrap_confirmed_response(response)
        data = response_data_mapping(response)
        if data is not None and bool(data.get("confirmation_required")):
            self._state.continue_invalidation(
                pending_id,
                response_confirmation_id(response),
                compound_invalidation,
            )
            return response
        if pending_id is not None and (
            (action == "deny" and response.success) or confirmation_consumed
        ):
            self._state.pending_invalidations.discard(pending_id)
        if confirmation_consumed:
            if response.success:
                await self._record_successful_action(
                    response,
                    params=params,
                    force_cdp_invalidation=compound_invalidation,
                )
            elif compound_invalidation:
                self._invalidate_cdp()
            return response
        if response.success:
            await self._record_successful_action(
                response,
                params=params,
                force_cdp_invalidation=compound_invalidation,
            )
        elif compound_invalidation:
            self._invalidate_cdp()
        return response

    def _pending_action(
        self,
        confirmation: ConfirmationRequired[Any] | BrowserResponse | str,
        *,
        decoder: Callable[[JSONMapping], T] | None = None,
        expect: Literal["object", "any"] = "object",
    ) -> AsyncPendingAction[T]:
        if isinstance(confirmation, BrowserResponse):
            pending_id = response_confirmation_id(confirmation)
            action = confirmation.action
            data = response_data_mapping(confirmation) or {}
        else:
            pending_id = confirmation_id(confirmation)
            if isinstance(confirmation, ConfirmationRequired):
                action = confirmation.action
                data = confirmation.data
            else:
                action = "confirm"
                data = {}
        if pending_id is None:
            raise ValueError("pending action requires a confirmation id")
        return AsyncPendingAction(
            _controller=self,
            confirmation_id=pending_id,
            action=action,
            details=dict(data),
            _decode=decoder,
            _expect=expect,
        )

    def _cdp(self) -> AsyncCDPController:
        if self._cdp_controller is None:
            from agentbrowser.cdp import AsyncCDPController

            self._cdp_controller = AsyncCDPController(AsyncBoundExecutor(self))
        return self._cdp_controller

    def _invalidate_cdp(self) -> None:
        if self._cdp_controller is not None:
            self._cdp_controller.invalidate()

    async def _reset_cdp(self) -> None:
        if self._cdp_controller is not None:
            await self._cdp_controller.close()
            self._cdp_controller = None

    async def _close_browser(self) -> CloseResult:
        if self._cdp_controller is not None:
            with suppress(Exception):
                await self._cdp_controller.close()
            self._cdp_controller = None
        response = await self._session.shutdown_native()
        if response is None:
            return CloseResult(closed=True)
        checked = _checked_response("close", replace(response, action="close"))
        await self._record_successful_action(checked)
        return close_result_from_data(_require_response_data_mapping(checked, action="close"))

    async def _close_once(self, *, timeout: float) -> CloseResult:
        result = CloseResult(closed=True)
        try:
            result = await asyncio.wait_for(self._close_browser(), timeout=timeout)
        finally:
            await self._session.aclose(timeout=timeout)
        if result.save_error is not None:
            raise RestoreSaveError(result)
        return result

    async def close(self, *, timeout: float = 5.0) -> CloseResult:
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close_once(timeout=timeout))
        return await asyncio.shield(self._close_task)
