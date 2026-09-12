from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.emulation.params import (
    geolocation_params,
    media_params,
    permissions_params,
    viewport_params,
)


@dataclass(frozen=True, slots=True)
class Emulation:
    """Browser environment and device emulation."""

    executor: Executor

    def viewport(
        self,
        width: int,
        height: int,
        *,
        device_scale_factor: float = 1.0,
        mobile: bool = False,
    ) -> None:
        """Set viewport dimensions in CSS pixels."""
        self.executor.execute(
            Command(
                "viewport",
                {
                    **viewport_params(
                        width, height, device_scale_factor=device_scale_factor, mobile=mobile
                    )
                },
                decode=lambda _data: None,
            )
        )

    def device(self, name: str) -> None:
        """Apply a named device preset."""
        self.executor.execute(Command("device", {"name": name}, decode=lambda _data: None))

    def headers(self, headers: Mapping[str, str]) -> None:
        """Set extra HTTP headers."""
        self.executor.execute(
            Command("headers", {"headers": dict(headers)}, decode=lambda _data: None)
        )

    def offline(self, enabled: bool = True) -> None:
        """Set network offline emulation."""
        self.executor.execute(Command("offline", {"offline": enabled}, decode=lambda _data: None))

    def user_agent(self, value: str) -> None:
        """Set the browser user agent."""
        self.executor.execute(Command("useragent", {"userAgent": value}, decode=lambda _data: None))

    def media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> None:
        """Set CSS media emulation."""
        self.executor.execute(
            Command(
                "set_media",
                {
                    **media_params(
                        media=media,
                        color_scheme=color_scheme,
                        reduced_motion=reduced_motion,
                        features=features,
                    )
                },
                decode=lambda _data: None,
            )
        )

    def timezone(self, timezone_id: str) -> None:
        """Set the emulated timezone."""
        self.executor.execute(
            Command("timezone", {"timezoneId": timezone_id}, decode=lambda _data: None)
        )

    def locale(self, locale: str) -> None:
        """Set the emulated locale."""
        self.executor.execute(Command("locale", {"locale": locale}, decode=lambda _data: None))

    def geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> None:
        """Set emulated coordinates."""
        self.executor.execute(
            Command(
                "geolocation",
                {**geolocation_params(latitude, longitude, accuracy=accuracy)},
                decode=lambda _data: None,
            )
        )

    def permissions(
        self,
        permissions: Sequence[str],
        *,
        origin: str | None = None,
    ) -> None:
        """Grant permissions for an optional origin."""
        self.executor.execute(
            Command(
                "permissions",
                {**permissions_params(permissions, origin=origin)},
                decode=lambda _data: None,
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncEmulation:
    """Async browser environment and device emulation."""

    executor: AsyncExecutor

    async def viewport(
        self,
        width: int,
        height: int,
        *,
        device_scale_factor: float = 1.0,
        mobile: bool = False,
    ) -> None:
        """Set viewport dimensions in CSS pixels."""
        await self.executor.execute(
            Command(
                "viewport",
                {
                    **viewport_params(
                        width, height, device_scale_factor=device_scale_factor, mobile=mobile
                    )
                },
                decode=lambda _data: None,
            )
        )

    async def device(self, name: str) -> None:
        """Apply a named device preset."""
        await self.executor.execute(Command("device", {"name": name}, decode=lambda _data: None))

    async def headers(self, headers: Mapping[str, str]) -> None:
        """Set extra HTTP headers."""
        await self.executor.execute(
            Command("headers", {"headers": dict(headers)}, decode=lambda _data: None)
        )

    async def offline(self, enabled: bool = True) -> None:
        """Set network offline emulation."""
        await self.executor.execute(
            Command("offline", {"offline": enabled}, decode=lambda _data: None)
        )

    async def user_agent(self, value: str) -> None:
        """Set the browser user agent."""
        await self.executor.execute(
            Command("useragent", {"userAgent": value}, decode=lambda _data: None)
        )

    async def media(
        self,
        *,
        media: str | None = None,
        color_scheme: str | None = None,
        reduced_motion: str | None = None,
        features: Mapping[str, str] | None = None,
    ) -> None:
        """Set CSS media emulation."""
        await self.executor.execute(
            Command(
                "set_media",
                {
                    **media_params(
                        media=media,
                        color_scheme=color_scheme,
                        reduced_motion=reduced_motion,
                        features=features,
                    )
                },
                decode=lambda _data: None,
            )
        )

    async def timezone(self, timezone_id: str) -> None:
        """Set the emulated timezone."""
        await self.executor.execute(
            Command("timezone", {"timezoneId": timezone_id}, decode=lambda _data: None)
        )

    async def locale(self, locale: str) -> None:
        """Set the emulated locale."""
        await self.executor.execute(
            Command("locale", {"locale": locale}, decode=lambda _data: None)
        )

    async def geolocation(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy: float | None = None,
    ) -> None:
        """Set emulated coordinates."""
        await self.executor.execute(
            Command(
                "geolocation",
                {**geolocation_params(latitude, longitude, accuracy=accuracy)},
                decode=lambda _data: None,
            )
        )

    async def permissions(
        self,
        permissions: Sequence[str],
        *,
        origin: str | None = None,
    ) -> None:
        """Grant permissions for an optional origin."""
        await self.executor.execute(
            Command(
                "permissions",
                {**permissions_params(permissions, origin=origin)},
                decode=lambda _data: None,
            )
        )
