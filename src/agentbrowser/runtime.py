"""Persistent Python execution with model-facing text and image results."""

from __future__ import annotations

import ast
import base64
import builtins
import inspect
import io
import threading
import traceback
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import CodeType
from typing import Any, Literal, TextIO, TypedDict
from uuid import uuid4

from agentbrowser.host import (
    BrowserTarget,
    CallbackHost,
    ExecutionContext,
    ImageContent,
    ImageDelivery,
    bind_host,
    reset_host,
)
from agentbrowser.tasks import Tasks, _ManagedHost


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str


class ImageBlock(TypedDict):
    type: Literal["image"]
    data: str
    mimeType: str


class CodeResult(TypedDict):
    """Model Context Protocol tool result with text and base64 image blocks."""

    content: list[TextBlock | ImageBlock]
    isError: bool


@dataclass
class _Output:
    content: list[TextBlock | ImageBlock] = field(default_factory=list)
    active: bool = True
    failed: bool = False

    def text(self, value: str) -> None:
        self.check_active()
        if not value:
            return
        if self.content and self.content[-1]["type"] == "text":
            block = self.content[-1]
            if block["type"] == "text":
                block["text"] += value
        else:
            self.content.append({"type": "text", "text": value})

    def image(self, content: ImageContent) -> ImageDelivery:
        self.check_active()
        self.content.append(
            {
                "type": "image",
                "data": base64.b64encode(content.data).decode("ascii"),
                "mimeType": content.media_type,
            }
        )
        return ImageDelivery("queued")

    def check_active(self) -> None:
        if not self.active:
            raise RuntimeError("code execution has ended, emit output during an active call")

    def result(self) -> CodeResult:
        return {"content": self.content, "isError": self.failed}


class CodeSession:
    """Execute trusted Python with persistent globals and image tool results.

    ``execute_code`` and ``aexecute_code`` return a JSON-serializable Model
    Context Protocol tool result. Hosts must forward its ``content`` blocks to
    the model as content, preserving each image block's type.

    ``print`` calls and the final expression produce text. Images emitted with
    ``current_host().emit_image(shot.content())`` appear in the same result.
    Imported libraries' writes to process stdout remain process output.

    Calls on one session must run sequentially. ``timeout_ms`` supplies the
    browser-operation budget. The calling host owns process isolation and
    interruption of arbitrary Python code.
    """

    def __init__(
        self,
        target: BrowserTarget | Callable[[], BrowserTarget],
        *,
        namespace: Mapping[str, Any] | None = None,
    ) -> None:
        self.target = target
        self.namespace: dict[str, Any] = dict(namespace or {})
        self.namespace.setdefault("__name__", "__agentbrowser__")
        self.namespace["__builtins__"] = {**vars(builtins), "print": self._print}
        self._output: ContextVar[_Output] = ContextVar("agentbrowser_code_output")
        self._lock = threading.Lock()
        self.tasks = Tasks(target)
        self._closed = False

    def execute_code(self, code: str, *, timeout_ms: int | None = None) -> CodeResult:
        """Execute Python and return ordered text and image content blocks.

        Exceptions produce ``isError=True`` and preserve output already emitted.
        Names assigned before an exception remain available in the next call.
        Concurrent calls raise ``RuntimeError``.
        """
        with self._execution(timeout_ms) as (output, result_name):
            compiled = self._compile(code, result_name, allow_await=False)
            exec(compiled, self.namespace)
            self._display_result(result_name, output)
        return output.result()

    async def aexecute_code(self, code: str, *, timeout_ms: int | None = None) -> CodeResult:
        """Execute Python with top-level await and return text and image blocks.

        Cancellation propagates to the caller after restoring the host binding.
        Awaited browser operations receive the current execution budget.
        """
        with self._execution(timeout_ms, managed_tasks=True) as (output, result_name):
            compiled = self._compile(code, result_name, allow_await=True)
            pending = eval(compiled, self.namespace)
            if inspect.isawaitable(pending):
                await pending
            self._display_result(result_name, output)
        return output.result()

    async def close(self) -> None:
        """Settle managed task cleanup and close this execution session.

        Objects supplied in ``namespace`` retain their caller-owned lifecycle.
        """
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("CodeSession is executing another call")
        try:
            self._closed = True
            await self.tasks.close()
        finally:
            self._lock.release()

    @contextmanager
    def _execution(
        self, timeout_ms: int | None, *, managed_tasks: bool = False
    ) -> Iterator[tuple[_Output, str]]:
        if self._closed:
            raise RuntimeError("CodeSession is closed")
        context = ExecutionContext(
            timeout_ms=timeout_ms, cancellation=managed_tasks, managed_tasks=managed_tasks
        )
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("CodeSession is executing another call")
        output = _Output()
        output_token = self._output.set(output)
        host = (
            _ManagedHost(self.target, output.image, context, tasks=self.tasks)
            if managed_tasks
            else CallbackHost(self.target, output.image, context)
        )
        host_token = bind_host(host)
        result_name = f"__agentbrowser_result_{uuid4().hex}"
        try:
            yield output, result_name
        except Exception as exc:
            output.failed = True
            output.text("".join(traceback.format_exception_only(type(exc), exc)))
        finally:
            self.namespace.pop(result_name, None)
            output.active = False
            reset_host(host_token)
            self._output.reset(output_token)
            self._lock.release()

    @staticmethod
    def _compile(code: str, result_name: str, *, allow_await: bool) -> CodeType:
        tree = ast.parse(code, filename="<agentbrowser>", mode="exec")
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            expression = tree.body[-1]
            tree.body[-1] = ast.copy_location(
                ast.Assign(
                    targets=[ast.Name(id=result_name, ctx=ast.Store())], value=expression.value
                ),
                expression,
            )
        ast.fix_missing_locations(tree)
        return compile(
            tree,
            "<agentbrowser>",
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT if allow_await else 0,
        )

    def _display_result(self, result_name: str, output: _Output) -> None:
        value = self.namespace.get(result_name)
        if value is not None:
            output.text(repr(value) + "\n")

    def _print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ) -> None:
        if file is not None:
            builtins.print(*values, sep=sep, end=end, file=file, flush=flush)
            return
        output = self._output.get(None)
        if output is None:
            raise RuntimeError("CodeSession print requires an active execution")
        stream = io.StringIO()
        builtins.print(*values, sep=sep, end=end, file=stream, flush=flush)
        output.text(stream.getvalue())
