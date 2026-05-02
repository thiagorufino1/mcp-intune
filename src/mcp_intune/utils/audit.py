import functools
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable

import structlog

logger = structlog.get_logger()
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def audited(fn: Callable) -> Callable:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        trace_id = str(uuid.uuid4())[:8]
        _trace_id.set(trace_id)
        tool_name = fn.__name__
        safe_kwargs = {k: v for k, v in kwargs.items() if k not in ("ctx",)}
        logger.info("tool_invoked", tool=tool_name, trace_id=trace_id, params=safe_kwargs)
        start = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info("tool_completed", tool=tool_name, trace_id=trace_id, elapsed_ms=elapsed_ms)
            return result
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("tool_failed", tool=tool_name, trace_id=trace_id, elapsed_ms=elapsed_ms, error=str(exc))
            raise

    return wrapper


def get_trace_id() -> str:
    return _trace_id.get()
