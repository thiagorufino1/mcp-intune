import asyncio
import time
import uuid
from typing import Any

import httpx
import structlog
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt

from mcp_intune.config import settings
from mcp_intune.graph.errors import (
    AuthError,
    BetaApiNotAllowedError,
    GraphValidationError,
    NotFoundError,
    ServiceUnavailableError,
    ThrottlingError,
)
from mcp_intune.security.auth import get_token

logger = structlog.get_logger()

GRAPH_BASE = "https://graph.microsoft.com"

_http_client: httpx.AsyncClient | None = None

_cache: dict[str, tuple[Any, float]] = {}
_cache_locks: dict[str, asyncio.Lock] = {}
_cache_meta_lock: asyncio.Lock | None = None


def _get_cache_meta_lock() -> asyncio.Lock:
    global _cache_meta_lock
    if _cache_meta_lock is None:
        _cache_meta_lock = asyncio.Lock()
    return _cache_meta_lock


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.graph_timeout_connect,
                read=settings.graph_timeout_read,
                write=10.0,
                pool=5.0,
            ),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
        )
    return _http_client


def clear_cache() -> None:
    global _http_client, _cache_meta_lock
    _cache.clear()
    _cache_locks.clear()
    _http_client = None
    _cache_meta_lock = None


def _assert_beta_allowed(path: str) -> None:
    if path.lstrip("/").startswith("beta/") and not settings.allow_beta_apis:
        raise BetaApiNotAllowedError(path)


async def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {await get_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "client-request-id": str(uuid.uuid4()),
    }


def _get_url(response: httpx.Response) -> str:
    try:
        return str(response.url)
    except RuntimeError:
        return "<unknown url>"


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 30))
        raise ThrottlingError(f"Graph throttled: {_get_url(response)}", retry_after_seconds=retry_after)
    if response.status_code == 404:
        raise NotFoundError(f"Resource not found: {_get_url(response)}")
    if response.status_code in (401, 403):
        raise AuthError(f"Auth error {response.status_code}: {_get_url(response)}")
    if response.status_code == 400:
        raise GraphValidationError(f"Validation error: {response.text}")
    if response.status_code >= 500:
        raise ServiceUnavailableError(f"Graph unavailable {response.status_code}: {_get_url(response)}")
    response.raise_for_status()


def _retry_wait(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, ThrottlingError):
        return float(exc.retry_after_seconds)
    attempt = retry_state.attempt_number
    return min(2 ** attempt * 2, 30)


@retry(
    retry=retry_if_exception_type((ThrottlingError, ServiceUnavailableError)),
    stop=stop_after_attempt(settings.graph_max_retries),
    wait=_retry_wait,
    reraise=True,
)
async def _do_request(method: str, url: str, json: Any = None, params: dict[str, Any] | None = None) -> Any:
    start = time.monotonic()
    response = await _get_http_client().request(method, url, headers=await _headers(), json=json, params=params)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.debug("graph_request", method=method, status=response.status_code, elapsed_ms=elapsed_ms)
    _raise_for_status(response)
    if response.status_code == 204:
        return {}
    if not response.content:
        logger.warning("graph_empty_body", status=response.status_code, url=_get_url(response))
        return {}
    return response.json()


async def _get_or_create_lock(cache_key: str) -> asyncio.Lock:
    async with _get_cache_meta_lock():
        if cache_key not in _cache_locks:
            _cache_locks[cache_key] = asyncio.Lock()
        return _cache_locks[cache_key]


async def graph_get(path: str, params: dict[str, Any] | None = None, ttl: int = 60) -> Any:
    _assert_beta_allowed(path)
    base_url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    # Use httpx to normalize the cache key (handles encoding consistently)
    cache_key = str(_get_http_client().build_request("GET", base_url, params=params).url)

    now = time.monotonic()
    if cache_key in _cache:
        data, expires_at = _cache[cache_key]
        if now < expires_at:
            logger.debug("graph_cache_hit", url=cache_key)
            return data

    lock = await _get_or_create_lock(cache_key)
    async with lock:
        if cache_key in _cache:
            data, expires_at = _cache[cache_key]
            if time.monotonic() < expires_at:  # fresh timestamp inside lock
                return data
        result = await _do_request("GET", base_url, params=params)
        _cache[cache_key] = (result, time.monotonic() + ttl)
        return result


async def graph_get_all_pages(path: str, params: dict[str, Any] | None = None) -> list[Any]:
    _assert_beta_allowed(path)
    base_url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    items: list[Any] = []
    # First page uses params (httpx encodes); subsequent nextLink URLs are already fully formed
    payload = await _do_request("GET", base_url, params=params)
    items.extend(payload.get("value", []))
    next_url: str | None = payload.get("@odata.nextLink")
    while next_url:
        payload = await _do_request("GET", next_url)
        items.extend(payload.get("value", []))
        next_url = payload.get("@odata.nextLink")
    return items


async def graph_get_paged(
    path: str, params: dict[str, Any] | None = None, top: int | None = None
) -> dict[str, Any]:
    _assert_beta_allowed(path)
    effective_top = top or settings.graph_default_top
    merged: dict[str, Any] = {**(params or {}), "$top": effective_top}
    base_url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    payload = await _do_request("GET", base_url, params=merged)
    return {
        "value": payload.get("value", []),
        "has_more": "@odata.nextLink" in payload,
        "next_cursor": payload.get("@odata.nextLink"),
        "total_count": payload.get("@odata.count"),
    }


async def graph_post(path: str, body: dict[str, Any]) -> Any:
    _assert_beta_allowed(path)
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    return await _do_request("POST", url, json=body)


async def graph_delete(path: str) -> dict[str, Any]:
    _assert_beta_allowed(path)
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    return await _do_request("DELETE", url)


async def _cache_cleanup_loop(interval_seconds: int = 300) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        now = time.monotonic()
        async with _get_cache_meta_lock():
            expired_keys = [k for k, (_, exp) in _cache.items() if now >= exp]
            for k in expired_keys:
                del _cache[k]
                _cache_locks.pop(k, None)


def build_batch(requests_list: list[dict[str, Any]]) -> dict[str, Any]:
    if len(requests_list) > 20:
        raise ValueError(
            f"Microsoft Graph supports up to 20 requests per batch, got {len(requests_list)}"
        )
    return {"requests": requests_list}
