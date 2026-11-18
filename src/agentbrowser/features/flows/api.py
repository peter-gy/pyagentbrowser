from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from agentbrowser.contracts.errors import BrowserError, ConfirmationRequired
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.flows.codec import (
    flow_recording_from_data,
    flow_run_error,
    flow_run_from_data,
    flow_summaries_from_data,
    saved_flow_from_data,
)
from agentbrowser.features.flows.models import FlowRecording, FlowRun, FlowSummary, SavedFlow
from agentbrowser.features.flows.params import flow_list_params, flow_run_params, flow_save_params


def _steps_command() -> Command[FlowRecording]:
    return Command("flow_steps", {}, decode=flow_recording_from_data)


def _save_command(
    name: str,
    *,
    params: Mapping[str, str] | None,
    description: str | None,
    output: str | None,
    from_step: int | None,
    to_step: int | None,
    timeout_ms: int | None,
) -> Command[SavedFlow]:
    return Command(
        "flow_save",
        flow_save_params(
            name,
            params=params,
            description=description,
            output=output,
            from_step=from_step,
            to_step=to_step,
            timeout_ms=timeout_ms,
        ),
        decode=saved_flow_from_data,
    )


def _run_command(
    name: str,
    *,
    params: Mapping[str, str] | None,
    origin: str | None,
    allow_writes: Literal["all"] | Sequence[str],
    where: Mapping[str, str] | None,
    fields: Sequence[str],
    limit: int | None,
    timeout_ms: int | None,
) -> Command[FlowRun]:
    return Command(
        "flow_run",
        flow_run_params(
            name,
            params=params,
            origin=origin,
            allow_writes=allow_writes,
            where=where,
            fields=fields,
            limit=limit,
            timeout_ms=timeout_ms,
        ),
        decode=flow_run_from_data,
    )


def _list_command(*, origin: str | None) -> Command[tuple[FlowSummary, ...]]:
    return Command("flow_list", flow_list_params(origin=origin), decode=flow_summaries_from_data)


@dataclass(frozen=True, slots=True)
class Flows:
    """Record, save, and run saved flows, an experimental feature of the engine.

    Recording needs a session launched with `LaunchOptions(capture=["flow"])`.
    """

    executor: Executor

    def steps(self) -> FlowRecording:
        """Return the commands recorded since capture started."""
        return self.executor.execute(_steps_command())

    def save(
        self,
        name: str,
        *,
        params: Mapping[str, str] | None = None,
        description: str | None = None,
        output: str | None = None,
        from_step: int | None = None,
        to_step: int | None = None,
        timeout_ms: int | None = None,
    ) -> SavedFlow:
        """Save recorded steps as a named flow, turning each `params` value into a parameter."""
        return self.executor.execute(
            _save_command(
                name,
                params=params,
                description=description,
                output=output,
                from_step=from_step,
                to_step=to_step,
                timeout_ms=timeout_ms,
            )
        )

    def run(
        self,
        name: str,
        *,
        params: Mapping[str, str] | None = None,
        origin: str | None = None,
        allow_writes: Literal["all"] | Sequence[str] = (),
        where: Mapping[str, str] | None = None,
        fields: Sequence[str] = (),
        limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> FlowRun:
        """Run a saved flow and return the JSON its output request answers with.

        A run sends the flow's requests to the site it was recorded on. A write
        outside `allow_writes` raises `ConfirmationRequired` before anything is
        sent. A run works before a browser is launched, because the HTTP tier
        needs none. A run the site stops raises `FlowRunError`.
        """
        command = _run_command(
            name,
            params=params,
            origin=origin,
            allow_writes=allow_writes,
            where=where,
            fields=fields,
            limit=limit,
            timeout_ms=timeout_ms,
        )
        try:
            return self.executor.execute(command)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map_error(flow_run_error)
            raise
        except BrowserError as error:
            mapped = flow_run_error(error)
            if mapped is error:
                raise
            raise mapped from error

    def list(self, *, origin: str | None = None) -> tuple[FlowSummary, ...]:
        """Return the flows saved on disk, optionally for one site."""
        return self.executor.execute(_list_command(origin=origin))


@dataclass(frozen=True, slots=True)
class AsyncFlows:
    """Async recording, saving, and running of saved flows, an experimental engine feature.

    Recording needs a session launched with `LaunchOptions(capture=["flow"])`.
    """

    executor: AsyncExecutor

    async def steps(self) -> FlowRecording:
        """Return the commands recorded since capture started."""
        return await self.executor.execute(_steps_command())

    async def save(
        self,
        name: str,
        *,
        params: Mapping[str, str] | None = None,
        description: str | None = None,
        output: str | None = None,
        from_step: int | None = None,
        to_step: int | None = None,
        timeout_ms: int | None = None,
    ) -> SavedFlow:
        """Save recorded steps as a named flow, turning each `params` value into a parameter."""
        return await self.executor.execute(
            _save_command(
                name,
                params=params,
                description=description,
                output=output,
                from_step=from_step,
                to_step=to_step,
                timeout_ms=timeout_ms,
            )
        )

    async def run(
        self,
        name: str,
        *,
        params: Mapping[str, str] | None = None,
        origin: str | None = None,
        allow_writes: Literal["all"] | Sequence[str] = (),
        where: Mapping[str, str] | None = None,
        fields: Sequence[str] = (),
        limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> FlowRun:
        """Run a saved flow and return the JSON its output request answers with.

        A run sends the flow's requests to the site it was recorded on. A write
        outside `allow_writes` raises `ConfirmationRequired` before anything is
        sent. A run works before a browser is launched, because the HTTP tier
        needs none. A run the site stops raises `FlowRunError`.
        """
        command = _run_command(
            name,
            params=params,
            origin=origin,
            allow_writes=allow_writes,
            where=where,
            fields=fields,
            limit=limit,
            timeout_ms=timeout_ms,
        )
        try:
            return await self.executor.execute(command)
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map_error(flow_run_error)
            raise
        except BrowserError as error:
            mapped = flow_run_error(error)
            if mapped is error:
                raise
            raise mapped from error

    async def list(self, *, origin: str | None = None) -> tuple[FlowSummary, ...]:
        """Return the flows saved on disk, optionally for one site."""
        return await self.executor.execute(_list_command(origin=origin))
