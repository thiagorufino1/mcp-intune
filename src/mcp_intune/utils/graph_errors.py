from typing import Any
from mcp_intune.graph.errors import (
    AuthError,
    BetaApiNotAllowedError,
    GraphError,
    NotFoundError,
    ServiceUnavailableError,
    ThrottlingError,
)


def graph_error_response(exc: Exception, context: str = "") -> dict[str, Any]:
    ctx = f" for {context}" if context else ""
    meta: dict[str, Any] = {"source": "graph", "api_version": "v1.0"}

    if isinstance(exc, NotFoundError):
        return {"status": "error", "errors": [f"Resource not found{ctx}."], "data": None, "meta": meta}
    if isinstance(exc, AuthError):
        return {
            "status": "error",
            "errors": [f"Authentication failed{ctx}. Check AZURE_CLIENT_SECRET and app permissions."],
            "data": None,
            "meta": meta,
        }
    if isinstance(exc, ThrottlingError):
        return {
            "status": "error",
            "errors": [f"Graph throttled{ctx}. Retry after {exc.retry_after_seconds}s."],
            "data": None,
            "meta": meta,
        }
    if isinstance(exc, BetaApiNotAllowedError):
        return {"status": "error", "errors": [str(exc)], "data": None, "meta": {**meta, "api_version": "beta"}}
    if isinstance(exc, GraphError):
        return {"status": "error", "errors": [f"Graph error{ctx}: {exc}"], "data": None, "meta": meta}
    return {"status": "error", "errors": [f"Unexpected error{ctx}: {exc}"], "data": None, "meta": meta}
