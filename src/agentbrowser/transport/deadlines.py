from __future__ import annotations

from time import monotonic


def command_parameters(params: dict[str, object]) -> dict[str, object]:
    """Preserve an explicit native command timeout across the worker queue."""
    result = dict(params)
    deadline = result.pop("_executionDeadline", None)
    timeout = result.get("_timeoutMs")
    if deadline is None:
        if timeout is None:
            return result
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("execution timeout must be a positive integer")
        deadline = monotonic() + timeout / 1_000
    if not isinstance(deadline, int | float):
        raise TypeError("execution deadline must be a monotonic timestamp")
    remaining = int((deadline - monotonic()) * 1_000)
    if remaining <= 0:
        raise TimeoutError("Command deadline reached before browser dispatch")
    result["_executionDeadline"] = deadline
    result["_timeoutMs"] = remaining
    return result
