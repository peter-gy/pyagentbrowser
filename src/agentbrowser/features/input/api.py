from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentbrowser.contracts.decode import none, required_string
from agentbrowser.contracts.protocol import optional
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.features.input.models import MouseButton, MouseEventType
from agentbrowser.features.input.params import keyboard_params, mouse_params, wheel_params


@dataclass(frozen=True, slots=True)
class Keyboard:
    """Keyboard typing, key press, and dispatch helpers."""

    executor: Executor

    def type(self, text: str) -> None:
        """Type text with the keyboard."""
        self.executor.execute(Command("keyboard", {"subaction": "type", "text": text}, decode=none))

    def insert_text(self, text: str) -> None:
        """Insert text without key events when supported."""
        self.executor.execute(
            Command("keyboard", {"subaction": "insertText", "text": text}, decode=none)
        )

    def press(self, key: str) -> None:
        """Press a key such as `Enter` or `Meta+K`."""
        self.executor.execute(Command("press", {"key": key}, decode=none))

    def down(self, key: str, *, code: str | None = None, text: str | None = None) -> None:
        """Dispatch a key-down event."""
        self.dispatch("keyDown", key=key, code=code, text=text)

    def up(self, key: str, *, code: str | None = None) -> None:
        """Dispatch a key-up event."""
        self.dispatch("keyUp", key=key, code=code)

    def dispatch(
        self,
        event_type: str,
        *,
        key: str | None = None,
        code: str | None = None,
        text: str | None = None,
    ) -> None:
        """Dispatch a low-level keyboard event."""
        self.executor.execute(
            Command(
                "keyboard",
                {**keyboard_params(event_type, key=key, code=code, text=text)},
                decode=none,
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncKeyboard:
    """Async keyboard typing, key press, and dispatch helpers."""

    executor: AsyncExecutor

    async def type(self, text: str) -> None:
        """Type text with the keyboard."""
        await self.executor.execute(
            Command("keyboard", {"subaction": "type", "text": text}, decode=none)
        )

    async def insert_text(self, text: str) -> None:
        """Insert text without key events when supported."""
        await self.executor.execute(
            Command("keyboard", {"subaction": "insertText", "text": text}, decode=none)
        )

    async def press(self, key: str) -> None:
        """Press a key such as `Enter` or `Meta+K`."""
        await self.executor.execute(Command("press", {"key": key}, decode=none))

    async def down(self, key: str, *, code: str | None = None, text: str | None = None) -> None:
        """Dispatch a key-down event."""
        await self.dispatch("keyDown", key=key, code=code, text=text)

    async def up(self, key: str, *, code: str | None = None) -> None:
        """Dispatch a key-up event."""
        await self.dispatch("keyUp", key=key, code=code)

    async def dispatch(
        self,
        event_type: str,
        *,
        key: str | None = None,
        code: str | None = None,
        text: str | None = None,
    ) -> None:
        """Dispatch a low-level keyboard event."""
        await self.executor.execute(
            Command(
                "keyboard",
                {**keyboard_params(event_type, key=key, code=code, text=text)},
                decode=none,
            )
        )


@dataclass(frozen=True, slots=True)
class Mouse:
    """Mouse movement, button, wheel, and dispatch helpers."""

    executor: Executor

    def move(self, x: float, y: float) -> None:
        """Move the mouse to page coordinates."""
        self.executor.execute(Command("mousemove", {"x": x, "y": y}, decode=none))

    def down(self, *, button: MouseButton = "left") -> None:
        """Press a mouse button."""
        self.executor.execute(Command("mousedown", {"button": button}, decode=none))

    def up(self, *, button: MouseButton = "left") -> None:
        """Release a mouse button."""
        self.executor.execute(Command("mouseup", {"button": button}, decode=none))

    def wheel(
        self,
        delta_y: float = 100,
        *,
        delta_x: float = 0,
        x: float = 0,
        y: float = 0,
    ) -> None:
        """Scroll with the mouse wheel."""
        self.executor.execute(
            Command("wheel", {**wheel_params(delta_y, delta_x=delta_x, x=x, y=y)}, decode=none)
        )

    def dispatch(
        self,
        event_type: MouseEventType,
        *,
        x: float = 0,
        y: float = 0,
        button: str = "none",
        click_count: int = 0,
    ) -> None:
        """Dispatch a low-level mouse event."""
        self.executor.execute(
            Command(
                "mouse",
                {**mouse_params(event_type, x=x, y=y, button=button, click_count=click_count)},
                decode=none,
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncMouse:
    """Async mouse movement, button, wheel, and dispatch helpers."""

    executor: AsyncExecutor

    async def move(self, x: float, y: float) -> None:
        """Move the mouse to page coordinates."""
        await self.executor.execute(Command("mousemove", {"x": x, "y": y}, decode=none))

    async def down(self, *, button: MouseButton = "left") -> None:
        """Press a mouse button."""
        await self.executor.execute(Command("mousedown", {"button": button}, decode=none))

    async def up(self, *, button: MouseButton = "left") -> None:
        """Release a mouse button."""
        await self.executor.execute(Command("mouseup", {"button": button}, decode=none))

    async def wheel(
        self,
        delta_y: float = 100,
        *,
        delta_x: float = 0,
        x: float = 0,
        y: float = 0,
    ) -> None:
        """Scroll with the mouse wheel."""
        await self.executor.execute(
            Command("wheel", {**wheel_params(delta_y, delta_x=delta_x, x=x, y=y)}, decode=none)
        )

    async def dispatch(
        self,
        event_type: MouseEventType,
        *,
        x: float = 0,
        y: float = 0,
        button: str = "none",
        click_count: int = 0,
    ) -> None:
        """Dispatch a low-level mouse event."""
        await self.executor.execute(
            Command(
                "mouse",
                {**mouse_params(event_type, x=x, y=y, button=button, click_count=click_count)},
                decode=none,
            )
        )


@dataclass(frozen=True, slots=True)
class Clipboard:
    """System clipboard helpers for the active browser context."""

    executor: Executor

    def read(self) -> str:
        """Read text from the clipboard."""
        return self.executor.execute(
            Command(
                "clipboard",
                {"subAction": "read"},
                decode=lambda data: required_string(data, "text", action="clipboard"),
            )
        )

    def write(self, text: str) -> None:
        """Write text to the clipboard."""
        self.executor.execute(
            Command("clipboard", {"subAction": "write", "text": text}, decode=none)
        )

    def copy(self) -> None:
        """Copy the current selection."""
        self.executor.execute(Command("clipboard", {"subAction": "copy"}, decode=none))

    def paste(self) -> None:
        """Paste clipboard content."""
        self.executor.execute(Command("clipboard", {"subAction": "paste"}, decode=none))


@dataclass(frozen=True, slots=True)
class AsyncClipboard:
    """Async system clipboard helpers for the active browser context."""

    executor: AsyncExecutor

    async def read(self) -> str:
        """Read text from the clipboard."""
        return await self.executor.execute(
            Command(
                "clipboard",
                {"subAction": "read"},
                decode=lambda data: required_string(data, "text", action="clipboard"),
            )
        )

    async def write(self, text: str) -> None:
        """Write text to the clipboard."""
        await self.executor.execute(
            Command("clipboard", {"subAction": "write", "text": text}, decode=none)
        )

    async def copy(self) -> None:
        """Copy the current selection."""
        await self.executor.execute(Command("clipboard", {"subAction": "copy"}, decode=none))

    async def paste(self) -> None:
        """Paste clipboard content."""
        await self.executor.execute(Command("clipboard", {"subAction": "paste"}, decode=none))


@dataclass(frozen=True, slots=True)
class Dialogs:
    """JavaScript dialog status and response helpers."""

    executor: Executor

    def status(self) -> Mapping[str, Any]:
        """Return current dialog status."""
        return self.executor.execute(Command("dialog", {"response": "status"}))

    def accept(self, prompt_text: str | None = None) -> None:
        """Accept the active dialog, optionally with prompt text."""
        self.executor.execute(
            Command(
                "dialog", {"response": "accept", "promptText": optional(prompt_text)}, decode=none
            )
        )

    def dismiss(self) -> None:
        """Dismiss the active dialog."""
        self.executor.execute(Command("dialog", {"response": "dismiss"}, decode=none))


@dataclass(frozen=True, slots=True)
class AsyncDialogs:
    """Async JavaScript dialog status and response helpers."""

    executor: AsyncExecutor

    async def status(self) -> Mapping[str, Any]:
        """Return current dialog status."""
        return await self.executor.execute(Command("dialog", {"response": "status"}))

    async def accept(self, prompt_text: str | None = None) -> None:
        """Accept the active dialog, optionally with prompt text."""
        await self.executor.execute(
            Command(
                "dialog", {"response": "accept", "promptText": optional(prompt_text)}, decode=none
            )
        )

    async def dismiss(self) -> None:
        """Dismiss the active dialog."""
        await self.executor.execute(Command("dialog", {"response": "dismiss"}, decode=none))
