import asyncio
import time
import uuid
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
    if "/beta/" in path and not settings.allow_beta_apis:
        raise BetaApiNotAllowedError(path)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_token()}",
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


@retry(
    retry=retry_if_exception_type((ThrottlingError, ServiceUnavailableError)),
    stop=stop_after_attempt(settings.graph_max_retries),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
)
async def _do_request(method: str, url: str, json: Any = None) -> Any:
    start = time.monotonic()
    response = await _get_http_client().request(method, url, headers=_headers(), json=json)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.debug("graph_request", method=method, status=response.status_code, elapsed_ms=elapsed_ms)
    _raise_for_status(response)
    return response.json()


async def _get_or_create_lock(cache_key: str) -> asyncio.Lock:
    async with _get_cache_meta_lock():
        if cache_key not in _cache_locks:
            _cache_locks[cache_key] = asyncio.Lock()
        return _cache_locks[cache_key]


async def graph_get(path: str, params: dict[str, Any] | None = None, ttl: int = 60) -> Any:
    _assert_beta_allowed(path)
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    now = time.monotonic()
    if url in _cache:
        data, expires_at = _cache[url]
        if now < expires_at:
            logger.debug("graph_cache_hit", url=url)
            return data

    lock = await _get_or_create_lock(url)
    async with lock:
        if url in _cache:
            data, expires_at = _cache[url]
            if now < expires_at:
                return data
        result = await _do_request("GET", url)
        _cache[url] = (result, time.monotonic() + ttl)
        return result


async def graph_get_all_pages(path: str, params: dict[str, Any] | None = None) -> list[Any]:
    _assert_beta_allowed(path)
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    items: list[Any] = []
    while url:
        payload = await _do_request("GET", url)
        items.extend(payload.get("value", []))
        url = payload.get("@odata.nextLink")  # type: ignore[assignment]
    return items


async def graph_get_paged(
    path: str, params: dict[str, Any] | None = None, top: int | None = None
) -> dict[str, Any]:
    _assert_beta_allowed(path)
    effective_top = top or settings.graph_default_top
    merged: dict[str, Any] = {**(params or {}), "$top": effective_top}
    url = f"{GRAPH_BASE}/{path.lstrip('/')}?" + "&".join(f"{k}={v}" for k, v in merged.items())

    payload = await _do_request("GET", url)
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


def build_batch(requests_list: list[dict[str, Any]]) -> dict[str, Any]:
    if len(requests_list) > 20:
        raise ValueError(
            f"Microsoft Graph suporta até 20 requests por batch, recebeu {len(requests_list)}"
        )
    return {"requests": requests_list}
