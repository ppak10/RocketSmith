"""Thin logging proxy for FastMCP tool registrations.

Wraps every tool registered via ``LoggingApp.tool()`` so that a
``source="tool_call"`` entry is written to ``session.jsonl`` at the start
and end of every invocation.  The tool implementations themselves need no
changes — simply pass a ``LoggingApp`` instance to each ``register_*``
function instead of the bare ``FastMCP`` app.

Entry format (extends the standard LogEntry schema)::

    {
        "timestamp": "...",
        "level": "info" | "success" | "error",
        "source": "tool_call",
        "tool": "openrocket_component",
        "status": "running" | "done" | "error",
        "message": "<tool_name or error text>",
        "detail": "<args summary or duration>"   # optional
    }
"""

from __future__ import annotations

import inspect
import json
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

# Tools to skip logging for (infrastructure / lifecycle tools).
_SKIP_TOOLS: frozenset[str] = frozenset(
    {"gui_server", "gui_navigate", "rocketsmith_setup"}
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _short(value: Any, max_len: int = 60) -> str:
    s = value if isinstance(value, str) else repr(value)
    return s[:max_len] + "…" if len(s) > max_len else s


def _args_summary(fn: Callable, args: tuple, kwargs: dict) -> str:
    """Return a compact human-readable summary of the call arguments."""
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        parts = [
            f"{k}={_short(v)}" for k, v in bound.arguments.items() if v is not None
        ]
        summary = ", ".join(parts)
        return summary[:140] + "…" if len(summary) > 140 else summary
    except Exception:
        return ""


def _project_dir_from_kwargs(kwargs: dict) -> Path:
    """Extract project_dir from tool kwargs, falling back to get_project_dir()."""
    from rocketsmith.mcp.utils import get_project_dir, resolve_path

    raw = kwargs.get("project_dir")
    if raw and isinstance(raw, (str, Path)):
        try:
            return resolve_path(raw)
        except Exception:
            pass
    return get_project_dir()


def _write(
    project_dir: Path,
    tool: str,
    status: str,
    level: str,
    message: str,
    detail: str | None,
) -> None:
    """Append a tool-call log entry to session.jsonl."""
    from rocketsmith.gui.layout import LOGS_DIR

    try:
        log_dir = project_dir / LOGS_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "source": "tool_call",
            "tool": tool,
            "status": status,
            "message": message,
        }
        if detail is not None:
            entry["detail"] = detail
        with open(log_dir / "session.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Never crash a tool because of logging.


# ── Wrapper factory ───────────────────────────────────────────────────────────


def _wrap(fn: Callable, tool_name: str) -> Callable:
    """Return a version of *fn* that logs to session.jsonl before and after."""
    is_async = inspect.iscoroutinefunction(fn)

    if is_async:

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            project_dir = _project_dir_from_kwargs(kwargs)
            args_str = _args_summary(fn, args, kwargs)
            _write(
                project_dir, tool_name, "running", "info", tool_name, args_str or None
            )
            t0 = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                ms = int((time.monotonic() - t0) * 1000)
                _result_log(project_dir, tool_name, result, ms)
                return result
            except Exception as exc:
                ms = int((time.monotonic() - t0) * 1000)
                _write(
                    project_dir,
                    tool_name,
                    "error",
                    "error",
                    f"{type(exc).__name__}: {str(exc)[:100]}",
                    f"{ms}ms",
                )
                raise

        return async_wrapper

    else:

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            project_dir = _project_dir_from_kwargs(kwargs)
            args_str = _args_summary(fn, args, kwargs)
            _write(
                project_dir, tool_name, "running", "info", tool_name, args_str or None
            )
            t0 = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                ms = int((time.monotonic() - t0) * 1000)
                _result_log(project_dir, tool_name, result, ms)
                return result
            except Exception as exc:
                ms = int((time.monotonic() - t0) * 1000)
                _write(
                    project_dir,
                    tool_name,
                    "error",
                    "error",
                    f"{type(exc).__name__}: {str(exc)[:100]}",
                    f"{ms}ms",
                )
                raise

        return sync_wrapper


def _result_log(project_dir: Path, tool_name: str, result: Any, ms: int) -> None:
    try:
        from rocketsmith.mcp.types import ToolError

        if isinstance(result, ToolError):
            _write(
                project_dir, tool_name, "error", "error", result.error[:120], f"{ms}ms"
            )
        else:
            _write(project_dir, tool_name, "done", "success", tool_name, f"{ms}ms")
    except Exception:
        _write(project_dir, tool_name, "done", "success", tool_name, f"{ms}ms")


# ── Proxy class ───────────────────────────────────────────────────────────────


class LoggingApp:
    """Drop-in proxy for ``FastMCP`` that wraps all ``.tool()`` registrations
    with session log entries.

    Usage::

        app = FastMCP(name="rocketsmith")
        logged = LoggingApp(app)

        register_openrocket_component(logged)  # instead of register_*(app)
        ...

        app.run()  # still run the real app
    """

    def __init__(self, app: FastMCP) -> None:
        self._app = app

    def tool(self, *args, **kwargs):
        """Proxy for ``app.tool(...)`` that injects logging."""

        # @logged.tool(name="foo", ...) — called with kwargs, returns decorator.
        def decorator(fn: Callable) -> Callable:
            tool_name = kwargs.get("name", fn.__name__)
            wrapped = fn if tool_name in _SKIP_TOOLS else _wrap(fn, tool_name)
            return self._app.tool(*args, **kwargs)(wrapped)

        # Handle @logged.tool (no-parens) edge case.
        if args and callable(args[0]) and not kwargs:
            fn = args[0]
            tool_name = fn.__name__
            wrapped = fn if tool_name in _SKIP_TOOLS else _wrap(fn, tool_name)
            return self._app.tool()(wrapped)

        return decorator

    def __getattr__(self, name: str) -> Any:
        # Transparently forward everything else (resource, prompt, run, …).
        return getattr(self._app, name)
