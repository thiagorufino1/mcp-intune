# MCP Intune V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only FastMCP server (HTTP+SSE) that exposes 7 Intune device tools via Microsoft Graph v1.0.

**Architecture:** Single Python process, 5-layer stack (tools → services → graph gateway → auth → Graph API). GraphGateway is a module-level singleton with in-memory TTL cache, tenacity retry, and full pagination support. All tools share the same response envelope and @audited decorator.

**Tech Stack:** Python 3.12, FastMCP ≥2.0, httpx, MSAL, pydantic-settings, tenacity, structlog, pytest + respx

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | deps, build, pytest config |
| `src/mcp_intune/__init__.py` | package marker |
| `src/mcp_intune/config.py` | pydantic-settings BaseSettings singleton |
| `src/mcp_intune/logging_config.py` | structlog JSON/console setup |
| `src/mcp_intune/graph/errors.py` | GraphError hierarchy |
| `src/mcp_intune/graph/client.py` | GraphGateway: GET, pagination, batch, cache, retry, beta flag |
| `src/mcp_intune/security/auth.py` | MSAL ConfidentialClientApplication singleton |
| `src/mcp_intune/schemas/entities/device.py` | Pydantic device models |
| `src/mcp_intune/schemas/responses/base.py` | ToolResponse envelope |
| `src/mcp_intune/utils/audit.py` | @audited decorator + trace_id ContextVar |
| `src/mcp_intune/utils/render.py` | ResponseFormat enum + render_response() |
| `src/mcp_intune/utils/graph_errors.py` | graph_error_response() helper |
| `src/mcp_intune/services/device/device_service.py` | 7 device service functions |
| `src/mcp_intune/tools/device/device_tools.py` | _register(mcp) + 7 @mcp.tool definitions |
| `src/mcp_intune/server.py` | FastMCP instance, lifespan, main() |
| `tests/conftest.py` | env vars, cache reset fixture |
| `tests/test_tool_registration.py` | FakeMCP registration check |
| `tests/test_graph_client.py` | GET, errors, pagination, batch, beta flag |
| `tests/test_device_service.py` | service functions with mocked graph_get |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/mcp_intune/__init__.py`
- Create: `src/mcp_intune/graph/__init__.py`
- Create: `src/mcp_intune/security/__init__.py`
- Create: `src/mcp_intune/tools/__init__.py`
- Create: `src/mcp_intune/tools/device/__init__.py`
- Create: `src/mcp_intune/services/__init__.py`
- Create: `src/mcp_intune/services/device/__init__.py`
- Create: `src/mcp_intune/schemas/__init__.py`
- Create: `src/mcp_intune/schemas/entities/__init__.py`
- Create: `src/mcp_intune/schemas/responses/__init__.py`
- Create: `src/mcp_intune/utils/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-intune"
version = "0.1.0"
description = "MCP server for Microsoft Intune support and operations"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0",
    "httpx>=0.27",
    "msal>=1.28",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "tenacity>=8.3",
    "structlog>=24.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.4",
    "mypy>=1.10",
]

[project.scripts]
mcp-intune = "mcp_intune.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/mcp_intune"]

[tool.pytest.ini_options]
asyncio_mode = "strict"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 2: Create .env.example**

```
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=

FASTMCP_TRANSPORT=http
FASTMCP_HOST=127.0.0.1
FASTMCP_PORT=8000

LOG_LEVEL=INFO
LOG_FORMAT=json
ALLOW_BETA_APIS=false

CACHE_TTL_DEVICE=60
CACHE_TTL_POLICY=120
CACHE_TTL_APP=300

GRAPH_TIMEOUT_CONNECT=10
GRAPH_TIMEOUT_READ=30
GRAPH_MAX_RETRIES=4
GRAPH_DEFAULT_TOP=50
```

- [ ] **Step 3: Create all `__init__.py` files (empty) and directory structure**

```bash
mkdir -p src/mcp_intune/graph src/mcp_intune/security
mkdir -p src/mcp_intune/tools/device src/mcp_intune/services/device
mkdir -p src/mcp_intune/schemas/entities src/mcp_intune/schemas/responses
mkdir -p src/mcp_intune/utils tests

touch src/mcp_intune/__init__.py
touch src/mcp_intune/graph/__init__.py
touch src/mcp_intune/security/__init__.py
touch src/mcp_intune/tools/__init__.py
touch src/mcp_intune/tools/device/__init__.py
touch src/mcp_intune/services/__init__.py
touch src/mcp_intune/services/device/__init__.py
touch src/mcp_intune/schemas/__init__.py
touch src/mcp_intune/schemas/entities/__init__.py
touch src/mcp_intune/schemas/responses/__init__.py
touch src/mcp_intune/utils/__init__.py
touch tests/__init__.py
```

- [ ] **Step 4: Create tests/conftest.py**

```python
import os
# Set env vars before any module imports settings singleton
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("FASTMCP_TRANSPORT", "http")
os.environ.setdefault("ALLOW_BETA_APIS", "false")
os.environ.setdefault("GRAPH_MAX_RETRIES", "1")  # 1 attempt = no retries, speeds up error tests

import pytest


@pytest.fixture(autouse=True)
def clear_graph_cache():
    # Defensive import: graph.client doesn't exist until Task 5
    try:
        from mcp_intune.graph.client import clear_cache
        clear_cache()
    except ImportError:
        pass
    yield
    try:
        from mcp_intune.graph.client import clear_cache
        clear_cache()
    except ImportError:
        pass
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: all packages install without error.

- [ ] **Step 6: Verify pytest discovers tests**

```bash
pytest --collect-only
```

Expected: `no tests ran` (no test files yet) — confirms pytest config works.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example src/ tests/
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Config and Logging

**Files:**
- Create: `src/mcp_intune/config.py`
- Create: `src/mcp_intune/logging_config.py`

- [ ] **Step 1: Write failing test for config**

Create `tests/test_config.py`:

```python
def test_settings_loads_from_env():
    from mcp_intune.config import settings
    assert settings.azure_tenant_id == "test-tenant-id"
    assert settings.azure_client_id == "test-client-id"
    assert settings.azure_client_secret.get_secret_value() == "test-client-secret"
    assert settings.allow_beta_apis is False
    assert settings.graph_default_top == 50
    assert settings.cache_ttl_device == 60
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_intune.config'`

- [ ] **Step 3: Create src/mcp_intune/config.py**

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: SecretStr

    fastmcp_transport: str = "http"
    fastmcp_host: str = "127.0.0.1"
    fastmcp_port: int = 8000

    log_level: str = "INFO"
    log_format: str = "json"
    allow_beta_apis: bool = False

    cache_ttl_device: int = 60
    cache_ttl_policy: int = 120
    cache_ttl_app: int = 300

    graph_timeout_connect: float = 10.0
    graph_timeout_read: float = 30.0
    graph_max_retries: int = 4
    graph_default_top: int = 50


settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: `PASSED`

- [ ] **Step 5: Create src/mcp_intune/logging_config.py**

No test needed — side-effectful setup function, validated at runtime.

```python
import logging
import os
import structlog


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json")

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "console":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
```

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/config.py src/mcp_intune/logging_config.py tests/test_config.py
git commit -m "feat: add config and logging"
```

---

## Task 3: Graph Error Hierarchy

**Files:**
- Create: `src/mcp_intune/graph/errors.py`
- Create: `tests/test_graph_errors.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_graph_errors.py`:

```python
from mcp_intune.graph.errors import (
    GraphError, ThrottlingError, NotFoundError,
    AuthError, GraphValidationError, ServiceUnavailableError, BetaApiNotAllowedError,
)


def test_throttling_error_stores_retry_after():
    exc = ThrottlingError("throttled", retry_after_seconds=45)
    assert isinstance(exc, GraphError)
    assert exc.retry_after_seconds == 45


def test_throttling_error_default_retry_after():
    exc = ThrottlingError("throttled")
    assert exc.retry_after_seconds == 30


def test_beta_api_not_allowed_error_message():
    exc = BetaApiNotAllowedError("/beta/deviceHealthScripts")
    assert "/beta/deviceHealthScripts" in str(exc)
    assert isinstance(exc, GraphError)


def test_all_errors_inherit_from_graph_error():
    for cls in [ThrottlingError, NotFoundError, AuthError,
                GraphValidationError, ServiceUnavailableError, BetaApiNotAllowedError]:
        exc = cls("msg") if cls not in (ThrottlingError, BetaApiNotAllowedError) else (
            cls("msg", retry_after_seconds=1) if cls == ThrottlingError else cls("/beta/test")
        )
        assert isinstance(exc, GraphError)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_graph_errors.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_intune.graph.errors'`

- [ ] **Step 3: Create src/mcp_intune/graph/errors.py**

```python
class GraphError(Exception):
    pass


class ThrottlingError(GraphError):
    def __init__(self, message: str, retry_after_seconds: int = 30) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class NotFoundError(GraphError):
    pass


class AuthError(GraphError):
    pass


class GraphValidationError(GraphError):
    pass


class ServiceUnavailableError(GraphError):
    pass


class BetaApiNotAllowedError(GraphError):
    def __init__(self, path: str) -> None:
        super().__init__(f"Beta API not allowed: {path}. Set ALLOW_BETA_APIS=true to enable.")
        self.path = path
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_graph_errors.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/graph/errors.py tests/test_graph_errors.py
git commit -m "feat: add graph error hierarchy"
```

---

## Task 4: MSAL Auth

**Files:**
- Create: `src/mcp_intune/security/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_auth.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from mcp_intune.graph.errors import AuthError


def test_get_token_returns_access_token():
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {"access_token": "fake-token-123"}

    with patch("mcp_intune.security.auth._get_app", return_value=mock_app):
        from mcp_intune.security.auth import get_token
        token = get_token()
        assert token == "fake-token-123"
        mock_app.acquire_token_for_client.assert_called_once_with(
            scopes=["https://graph.microsoft.com/.default"]
        )


def test_get_token_raises_auth_error_on_failure():
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "AADSTS70011: Invalid client secret",
    }

    with patch("mcp_intune.security.auth._get_app", return_value=mock_app):
        from mcp_intune.security.auth import get_token
        with pytest.raises(AuthError, match="Failed to acquire token"):
            get_token()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_intune.security.auth'`

- [ ] **Step 3: Create src/mcp_intune/security/auth.py**

```python
import threading
from msal import ConfidentialClientApplication
from mcp_intune.config import settings
from mcp_intune.graph.errors import AuthError

_app: ConfidentialClientApplication | None = None
_lock = threading.Lock()


def _get_app() -> ConfidentialClientApplication:
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                _app = ConfidentialClientApplication(
                    client_id=settings.azure_client_id,
                    authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
                    client_credential=settings.azure_client_secret.get_secret_value(),
                )
    return _app


def get_token() -> str:
    app = _get_app()
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise AuthError(
            f"Failed to acquire token: {result.get('error_description', result.get('error', 'unknown'))}"
        )
    return result["access_token"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_auth.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/security/auth.py tests/test_auth.py
git commit -m "feat: add MSAL auth singleton"
```

---

## Task 5: GraphGateway

**Files:**
- Create: `src/mcp_intune/graph/client.py`
- Create: `tests/test_graph_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_graph_client.py`:

```python
import pytest
import respx
import httpx
from unittest.mock import patch


DEVICE_URL = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices/abc-123"
BETA_URL = "https://graph.microsoft.com/beta/deviceManagement/deviceHealthScripts"


@pytest.fixture
def mock_token():
    with patch("mcp_intune.graph.client.get_token", return_value="fake-token"):
        yield


# --- _raise_for_status ---

def test_raise_for_status_429_raises_throttling_error():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import ThrottlingError
    response = httpx.Response(429, headers={"Retry-After": "45"}, json={})
    with pytest.raises(ThrottlingError) as exc_info:
        _raise_for_status(response)
    assert exc_info.value.retry_after_seconds == 45


def test_raise_for_status_404_raises_not_found():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import NotFoundError
    response = httpx.Response(404, json={"error": {"message": "Not found"}})
    with pytest.raises(NotFoundError):
        _raise_for_status(response)


def test_raise_for_status_401_raises_auth_error():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import AuthError
    response = httpx.Response(401, json={"error": {"message": "Unauthorized"}})
    with pytest.raises(AuthError):
        _raise_for_status(response)


def test_raise_for_status_500_raises_service_unavailable():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import ServiceUnavailableError
    response = httpx.Response(503, json={})
    with pytest.raises(ServiceUnavailableError):
        _raise_for_status(response)


# --- beta flag ---

def test_beta_api_blocked_when_flag_false():
    from mcp_intune.graph.client import _assert_beta_allowed
    from mcp_intune.graph.errors import BetaApiNotAllowedError
    with pytest.raises(BetaApiNotAllowedError):
        _assert_beta_allowed("/beta/deviceManagement/deviceHealthScripts")


def test_v1_api_always_allowed():
    from mcp_intune.graph.client import _assert_beta_allowed
    _assert_beta_allowed("/v1.0/deviceManagement/managedDevices")  # no exception


# --- graph_get ---

@pytest.mark.asyncio
async def test_graph_get_returns_data(mock_token):
    with respx.mock:
        respx.get(DEVICE_URL).mock(
            return_value=httpx.Response(200, json={"id": "abc-123", "deviceName": "LAP-001"})
        )
        from mcp_intune.graph.client import graph_get
        result = await graph_get("v1.0/deviceManagement/managedDevices/abc-123", ttl=60)
        assert result["id"] == "abc-123"
        assert result["deviceName"] == "LAP-001"


@pytest.mark.asyncio
async def test_graph_get_caches_response(mock_token):
    with respx.mock:
        route = respx.get(DEVICE_URL).mock(
            return_value=httpx.Response(200, json={"id": "abc-123"})
        )
        from mcp_intune.graph.client import graph_get
        await graph_get("v1.0/deviceManagement/managedDevices/abc-123", ttl=60)
        await graph_get("v1.0/deviceManagement/managedDevices/abc-123", ttl=60)
        assert route.call_count == 1  # second call served from cache


@pytest.mark.asyncio
async def test_graph_get_all_pages_follows_next_link(mock_token):
    page1_url = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
    page2_url = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices?$skiptoken=page2"

    with respx.mock:
        respx.get(page1_url).mock(return_value=httpx.Response(200, json={
            "value": [{"id": "1"}, {"id": "2"}],
            "@odata.nextLink": page2_url,
        }))
        respx.get(page2_url).mock(return_value=httpx.Response(200, json={
            "value": [{"id": "3"}],
        }))
        from mcp_intune.graph.client import graph_get_all_pages
        items = await graph_get_all_pages("v1.0/deviceManagement/managedDevices")
        assert len(items) == 3
        assert [i["id"] for i in items] == ["1", "2", "3"]


# --- build_batch ---

def test_build_batch_accepts_20_requests():
    from mcp_intune.graph.client import build_batch
    requests = [{"id": str(i), "method": "GET", "url": f"/v1.0/test/{i}"} for i in range(20)]
    result = build_batch(requests)
    assert len(result["requests"]) == 20


def test_build_batch_rejects_21_requests():
    from mcp_intune.graph.client import build_batch
    requests = [{"id": str(i), "method": "GET", "url": f"/v1.0/test/{i}"} for i in range(21)]
    with pytest.raises(ValueError, match="20"):
        build_batch(requests)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_graph_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_intune.graph.client'`

- [ ] **Step 3: Create src/mcp_intune/graph/client.py**

```python
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

_http_client: httpx.AsyncClient = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=settings.graph_timeout_connect,
        read=settings.graph_timeout_read,
        write=10.0,
        pool=5.0,
    ),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
)

_cache: dict[str, tuple[Any, float]] = {}
_cache_locks: dict[str, asyncio.Lock] = {}
_cache_meta_lock = asyncio.Lock()


def clear_cache() -> None:
    _cache.clear()
    _cache_locks.clear()


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


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 30))
        raise ThrottlingError(f"Graph throttled: {response.url}", retry_after_seconds=retry_after)
    if response.status_code == 404:
        raise NotFoundError(f"Resource not found: {response.url}")
    if response.status_code in (401, 403):
        raise AuthError(f"Auth error {response.status_code}: {response.url}")
    if response.status_code == 400:
        raise GraphValidationError(f"Validation error: {response.text}")
    if response.status_code >= 500:
        raise ServiceUnavailableError(f"Graph unavailable {response.status_code}: {response.url}")
    response.raise_for_status()


@retry(
    retry=retry_if_exception_type((ThrottlingError, ServiceUnavailableError)),
    stop=stop_after_attempt(settings.graph_max_retries),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
)
async def _do_request(method: str, url: str, json: Any = None) -> Any:
    start = time.monotonic()
    response = await _http_client.request(method, url, headers=_headers(), json=json)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.debug("graph_request", method=method, status=response.status_code, elapsed_ms=elapsed_ms)
    _raise_for_status(response)
    return response.json()


async def _get_or_create_lock(cache_key: str) -> asyncio.Lock:
    async with _cache_meta_lock:
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_graph_client.py -v
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/graph/client.py tests/test_graph_client.py
git commit -m "feat: add GraphGateway with cache, pagination, retry, and batch"
```

---

## Task 6: Schemas and Utils

**Files:**
- Create: `src/mcp_intune/schemas/entities/device.py`
- Create: `src/mcp_intune/schemas/responses/base.py`
- Create: `src/mcp_intune/utils/audit.py`
- Create: `src/mcp_intune/utils/render.py`
- Create: `src/mcp_intune/utils/graph_errors.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_utils.py`:

```python
import asyncio
import json
import pytest
from mcp_intune.utils.render import ResponseFormat, render_response
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.graph.errors import ThrottlingError, NotFoundError, BetaApiNotAllowedError


# --- render ---

def test_render_response_json_returns_valid_json():
    data = {"id": "123", "deviceName": "LAP-001", "count": 5}
    result = render_response(data, ResponseFormat.JSON)
    parsed = json.loads(result)
    assert parsed["id"] == "123"


def test_render_response_markdown_returns_string():
    data = {"id": "123", "deviceName": "LAP-001"}
    result = render_response(data, ResponseFormat.MARKDOWN)
    assert isinstance(result, str)
    assert "LAP-001" in result


def test_render_response_markdown_skips_none_values():
    data = {"id": "123", "emptyField": None, "deviceName": "LAP-001"}
    result = render_response(data, ResponseFormat.MARKDOWN)
    assert "emptyField" not in result


# --- graph_error_response ---

def test_graph_error_response_not_found():
    exc = NotFoundError("not found")
    result = graph_error_response(exc, context="device 'abc'")
    assert result["status"] == "error"
    assert "not found" in result["errors"][0].lower()


def test_graph_error_response_throttling():
    exc = ThrottlingError("throttled", retry_after_seconds=30)
    result = graph_error_response(exc, context="search")
    assert result["status"] == "error"
    assert "30" in result["errors"][0]


def test_graph_error_response_beta_not_allowed():
    exc = BetaApiNotAllowedError("/beta/test")
    result = graph_error_response(exc)
    assert result["status"] == "error"


# --- @audited decorator ---

@pytest.mark.asyncio
async def test_audited_decorator_passes_through_result():
    from mcp_intune.utils.audit import audited

    @audited
    async def my_tool(device_id: str) -> str:
        return f"result for {device_id}"

    result = await my_tool(device_id="abc-123")
    assert result == "result for abc-123"


@pytest.mark.asyncio
async def test_audited_decorator_re_raises_exceptions():
    from mcp_intune.utils.audit import audited

    @audited
    async def failing_tool() -> str:
        raise ValueError("something went wrong")

    with pytest.raises(ValueError, match="something went wrong"):
        await failing_tool()


@pytest.mark.asyncio
async def test_audited_sets_trace_id():
    from mcp_intune.utils.audit import audited, get_trace_id

    captured_trace_id: list[str] = []

    @audited
    async def my_tool() -> str:
        captured_trace_id.append(get_trace_id())
        return "ok"

    await my_tool()
    assert len(captured_trace_id[0]) == 8
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_utils.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create src/mcp_intune/schemas/entities/device.py**

```python
from datetime import datetime
from pydantic import BaseModel


class DeviceSummary(BaseModel):
    id: str
    deviceName: str | None = None
    serialNumber: str | None = None
    operatingSystem: str | None = None
    osVersion: str | None = None
    complianceState: str | None = None
    lastSyncDateTime: datetime | None = None
    userPrincipalName: str | None = None
    manufacturer: str | None = None
    model: str | None = None


class DetectedApp(BaseModel):
    id: str
    displayName: str | None = None
    version: str | None = None
    publisher: str | None = None
    sizeInByte: int | None = None


class CompliancePolicyState(BaseModel):
    id: str
    displayName: str | None = None
    state: str | None = None
    settingCount: int | None = None
    errorCount: int | None = None
    conflictCount: int | None = None


class ConfigurationState(BaseModel):
    id: str
    displayName: str | None = None
    state: str | None = None
    version: int | None = None
    errorCount: int | None = None
    conflictCount: int | None = None
```

- [ ] **Step 4: Create src/mcp_intune/schemas/responses/base.py**

```python
import uuid
from typing import Any
from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    source: str = "graph"
    api_version: str = "v1.0"
    cached: bool = False
    next_cursor: str | None = None


class ToolResponse(BaseModel):
    status: str
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data: Any = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)

    @classmethod
    def ok(cls, data: Any, **meta_kwargs: Any) -> "ToolResponse":
        return cls(status="ok", data=data, meta=ResponseMeta(**meta_kwargs))

    @classmethod
    def error(cls, errors: list[str], **meta_kwargs: Any) -> "ToolResponse":
        return cls(status="error", errors=errors, meta=ResponseMeta(**meta_kwargs))
```

- [ ] **Step 5: Create src/mcp_intune/utils/audit.py**

```python
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
```

- [ ] **Step 6: Create src/mcp_intune/utils/render.py**

```python
import json
from enum import Enum
from typing import Any


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


def render_response(data: Any, response_format: ResponseFormat) -> str:
    if response_format == ResponseFormat.JSON:
        if hasattr(data, "model_dump"):
            return json.dumps(data.model_dump(), default=str, indent=2)
        return json.dumps(data, default=str, indent=2)
    if hasattr(data, "model_dump"):
        return _dict_to_markdown(data.model_dump())
    if isinstance(data, dict):
        return _dict_to_markdown(data)
    if isinstance(data, list):
        return "\n\n".join(_dict_to_markdown(item) if isinstance(item, dict) else str(item) for item in data[:20])
    return str(data)


def _dict_to_markdown(d: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    for key, value in d.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}:**")
            lines.append(_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}:** ({len(value)} items)")
            for item in value[:10]:
                if isinstance(item, dict):
                    lines.append(_dict_to_markdown(item, indent + 1))
                    lines.append("")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}**{key}:** {value}")
    return "\n".join(lines)
```

- [ ] **Step 7: Create src/mcp_intune/utils/graph_errors.py**

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_utils.py -v
```

Expected: `9 passed`

- [ ] **Step 9: Commit**

```bash
git add src/mcp_intune/schemas/ src/mcp_intune/utils/ tests/test_utils.py
git commit -m "feat: add schemas, audit decorator, render utils, and error helpers"
```

---

## Task 7: Device Service

**Files:**
- Create: `src/mcp_intune/services/device/device_service.py`
- Create: `tests/test_device_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_device_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch


DEVICE_STUB = {
    "id": "abc-123",
    "deviceName": "LAP-001",
    "manufacturer": "Dell",
    "model": "Latitude 7440",
    "serialNumber": "SN-XYZ",
    "operatingSystem": "Windows",
    "osVersion": "11 23H2",
    "complianceState": "noncompliant",
    "lastSyncDateTime": "2026-05-01T12:00:00Z",
    "userPrincipalName": "user@empresa.com",
}

COMPLIANCE_STATES_STUB = {
    "value": [
        {"id": "p1", "displayName": "Require BitLocker", "state": "nonCompliant", "errorCount": 0},
        {"id": "p2", "displayName": "Require Antivirus", "state": "compliant", "errorCount": 0},
    ]
}

DETECTED_APPS_STUB = [
    {"id": "app1", "displayName": "Chrome", "version": "124.0", "publisher": "Google"},
    {"id": "app2", "displayName": "Teams", "version": "2.0", "publisher": "Microsoft"},
]

CONFIG_STATES_STUB = {
    "value": [
        {"id": "cfg1", "displayName": "Windows Security Baseline", "state": "error", "errorCount": 2},
    ]
}

SEARCH_RESULT_STUB = {
    "value": [DEVICE_STUB],
    "has_more": False,
    "next_cursor": None,
    "total_count": None,
}


@pytest.mark.asyncio
async def test_search_devices_calls_graph_get_paged():
    with patch("mcp_intune.services.device.device_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = SEARCH_RESULT_STUB
        from mcp_intune.services.device.device_service import search_devices
        result = await search_devices(query="LAP-001")
        assert result["value"][0]["deviceName"] == "LAP-001"
        mock_paged.assert_called_once()
        call_kwargs = mock_paged.call_args
        assert "LAP-001" in str(call_kwargs)


@pytest.mark.asyncio
async def test_search_devices_with_platform_filter():
    with patch("mcp_intune.services.device.device_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = SEARCH_RESULT_STUB
        from mcp_intune.services.device.device_service import search_devices
        await search_devices(query="LAP", platform="Windows")
        call_args = mock_paged.call_args
        params = call_args[1].get("params") or call_args[0][1]
        assert "Windows" in str(params)


@pytest.mark.asyncio
async def test_get_device_hardware_returns_device_data():
    with patch("mcp_intune.services.device.device_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = DEVICE_STUB
        from mcp_intune.services.device.device_service import get_device_hardware
        result = await get_device_hardware("abc-123")
        assert result["deviceName"] == "LAP-001"
        assert result["serialNumber"] == "SN-XYZ"
        call_path = mock_get.call_args[0][0]
        assert "abc-123" in call_path
        assert "$select" in str(mock_get.call_args)


@pytest.mark.asyncio
async def test_get_device_users_calls_users_endpoint():
    with patch("mcp_intune.services.device.device_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"value": [{"id": "u1", "userPrincipalName": "user@empresa.com"}]}
        from mcp_intune.services.device.device_service import get_device_users
        result = await get_device_users("abc-123")
        assert result["value"][0]["userPrincipalName"] == "user@empresa.com"
        call_path = mock_get.call_args[0][0]
        assert "users" in call_path


@pytest.mark.asyncio
async def test_get_detected_apps_returns_all_pages():
    with patch("mcp_intune.services.device.device_service.graph_get_all_pages", new_callable=AsyncMock) as mock_pages:
        mock_pages.return_value = DETECTED_APPS_STUB
        from mcp_intune.services.device.device_service import get_detected_apps
        result = await get_detected_apps("abc-123")
        assert len(result) == 2
        assert result[0]["displayName"] == "Chrome"
        call_path = mock_pages.call_args[0][0]
        assert "detectedApps" in call_path


@pytest.mark.asyncio
async def test_get_compliance_state_returns_device_and_policy_states():
    with patch("mcp_intune.services.device.device_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [DEVICE_STUB, COMPLIANCE_STATES_STUB]
        from mcp_intune.services.device.device_service import get_compliance_state
        result = await get_compliance_state("abc-123")
        assert result["device"]["complianceState"] == "noncompliant"
        assert len(result["compliancePolicyStates"]) == 2
        assert result["compliancePolicyStates"][0]["state"] == "nonCompliant"


@pytest.mark.asyncio
async def test_get_policy_status_returns_config_states():
    with patch("mcp_intune.services.device.device_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = CONFIG_STATES_STUB
        from mcp_intune.services.device.device_service import get_policy_status
        result = await get_policy_status("abc-123")
        assert len(result["configurationStates"]) == 1
        assert result["configurationStates"][0]["state"] == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_device_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_intune.services.device.device_service'`

- [ ] **Step 3: Create src/mcp_intune/services/device/device_service.py**

```python
import asyncio
from typing import Any

from mcp_intune.config import settings
from mcp_intune.graph.client import graph_get, graph_get_all_pages, graph_get_paged

DEVICE_BASE = "v1.0/deviceManagement/managedDevices"

HARDWARE_SELECT = ",".join([
    "id", "deviceName", "manufacturer", "model", "serialNumber",
    "totalStorageSpaceInBytes", "freeStorageSpaceInBytes",
    "physicalMemoryInBytes", "operatingSystem", "osVersion",
])

OVERVIEW_SELECT = ",".join([
    "id", "deviceName", "manufacturer", "model", "serialNumber",
    "operatingSystem", "osVersion", "complianceState",
    "lastSyncDateTime", "userPrincipalName", "managementState",
    "enrolledDateTime", "deviceEnrollmentType", "azureADDeviceId",
    "managedDeviceOwnerType",
])


async def search_devices(
    query: str,
    platform: str | None = None,
    compliance_state: str | None = None,
    top: int | None = None,
) -> dict[str, Any]:
    filter_parts = [
        f"(startswith(deviceName,'{query}') or serialNumber eq '{query}' or userPrincipalName eq '{query}')"
    ]
    if platform:
        filter_parts.append(f"operatingSystem eq '{platform}'")
    if compliance_state:
        filter_parts.append(f"complianceState eq '{compliance_state}'")

    params = {
        "$filter": " and ".join(filter_parts),
        "$select": "id,deviceName,serialNumber,operatingSystem,osVersion,complianceState,lastSyncDateTime,userPrincipalName,manufacturer,model",
    }
    return await graph_get_paged(DEVICE_BASE, params=params, top=top)


async def get_device_overview(device_id: str, include: list[str] | None = None) -> dict[str, Any]:
    include = include or []
    device = await graph_get(
        f"{DEVICE_BASE}/{device_id}",
        params={"$select": OVERVIEW_SELECT},
        ttl=settings.cache_ttl_device,
    )

    coroutines: dict[str, Any] = {}
    if not include or "primaryUser" in include:
        coroutines["users"] = graph_get(f"{DEVICE_BASE}/{device_id}/users", ttl=settings.cache_ttl_device)
    if not include or "compliance" in include:
        coroutines["compliance_states"] = graph_get(
            f"{DEVICE_BASE}/{device_id}/deviceCompliancePolicyStates",
            ttl=settings.cache_ttl_policy,
        )
    if "policies" in include:
        coroutines["config_states"] = graph_get(
            f"{DEVICE_BASE}/{device_id}/deviceConfigurationStates",
            ttl=settings.cache_ttl_policy,
        )
    if "detectedApps" in include:
        coroutines["detected_apps"] = graph_get_all_pages(f"{DEVICE_BASE}/{device_id}/detectedApps")

    extras: dict[str, Any] = {}
    if coroutines:
        resolved = await asyncio.gather(*coroutines.values(), return_exceptions=True)
        for key, result in zip(coroutines.keys(), resolved):
            extras[key] = {"error": str(result)} if isinstance(result, Exception) else result

    return {"device": device, **extras}


async def get_device_hardware(device_id: str) -> dict[str, Any]:
    return await graph_get(
        f"{DEVICE_BASE}/{device_id}",
        params={"$select": HARDWARE_SELECT},
        ttl=settings.cache_ttl_device,
    )


async def get_device_users(device_id: str) -> dict[str, Any]:
    return await graph_get(f"{DEVICE_BASE}/{device_id}/users", ttl=settings.cache_ttl_device)


async def get_detected_apps(device_id: str) -> list[Any]:
    return await graph_get_all_pages(f"{DEVICE_BASE}/{device_id}/detectedApps")


async def get_compliance_state(device_id: str) -> dict[str, Any]:
    device, policy_states = await asyncio.gather(
        graph_get(
            f"{DEVICE_BASE}/{device_id}",
            params={"$select": "id,deviceName,complianceState,lastSyncDateTime,userPrincipalName"},
            ttl=settings.cache_ttl_device,
        ),
        graph_get(
            f"{DEVICE_BASE}/{device_id}/deviceCompliancePolicyStates",
            ttl=settings.cache_ttl_policy,
        ),
    )
    return {
        "device": device,
        "compliancePolicyStates": policy_states.get("value", []),
    }


async def get_policy_status(device_id: str, policy_type: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if policy_type:
        params["$filter"] = f"platformType eq '{policy_type}'"

    result = await graph_get(
        f"{DEVICE_BASE}/{device_id}/deviceConfigurationStates",
        params=params or None,
        ttl=settings.cache_ttl_policy,
    )
    return {"configurationStates": result.get("value", [])}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_device_service.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/device/device_service.py tests/test_device_service.py
git commit -m "feat: add device service layer"
```

---

## Task 8: Device Tools

**Files:**
- Create: `src/mcp_intune/tools/device/device_tools.py`
- Create: `tests/test_tool_registration.py`

- [ ] **Step 1: Write failing registration test**

Create `tests/test_tool_registration.py`:

```python
from typing import Any


class FakeMCP:
    """Minimal FastMCP stub for registration tests."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, name: str, annotations: dict | None = None):
        def decorator(fn: Any) -> Any:
            self.tools[name] = fn
            return fn
        return decorator


EXPECTED_TOOLS = [
    "intune_search_devices",
    "intune_get_device_overview",
    "intune_get_device_hardware",
    "intune_get_device_users",
    "intune_get_detected_apps",
    "intune_get_compliance_state",
    "intune_get_policy_status",
]


def test_all_device_tools_registered():
    from mcp_intune.tools.device.device_tools import _register
    fake = FakeMCP()
    _register(fake)
    for tool_name in EXPECTED_TOOLS:
        assert tool_name in fake.tools, f"Tool '{tool_name}' not registered"


def test_no_extra_tools_registered():
    from mcp_intune.tools.device.device_tools import _register
    fake = FakeMCP()
    _register(fake)
    assert len(fake.tools) == len(EXPECTED_TOOLS), (
        f"Expected {len(EXPECTED_TOOLS)} tools, got {len(fake.tools)}: {list(fake.tools)}"
    )


def test_all_tools_have_intune_prefix():
    from mcp_intune.tools.device.device_tools import _register
    fake = FakeMCP()
    _register(fake)
    for name in fake.tools:
        assert name.startswith("intune_"), f"Tool '{name}' missing 'intune_' prefix"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_tool_registration.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_intune.tools.device.device_tools'`

- [ ] **Step 3: Create src/mcp_intune/tools/device/device_tools.py**

```python
from typing import Any

import fastmcp

from mcp_intune.services.device import device_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_search_devices", annotations={**_ANNOTATIONS, "title": "Search Intune Devices"})
    @audited
    async def intune_search_devices(
        query: str,
        platform: str | None = None,
        compliance_state: str | None = None,
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Search Intune managed devices by device name (prefix), serial number (exact), or UPN (exact).

        USE: Find a device before calling get_device_overview or get_compliance_state.
        DON'T USE: For listing all devices without a query — use export_report instead.

        Args:
            query: Device name prefix, exact serial number, or exact user UPN.
            platform: Optional OS filter — 'Windows', 'iOS', 'Android', 'macOS'.
            compliance_state: Optional filter — 'compliant', 'noncompliant', 'unknown'.
            top: Max results per page (default 50, max 999).
        """
        try:
            result = await device_service.search_devices(query, platform, compliance_state, top)
        except Exception as exc:
            result = graph_error_response(exc, context=f"search '{query}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_device_overview", annotations={**_ANNOTATIONS, "title": "Get Device Overview"})
    @audited
    async def intune_get_device_overview(
        device_id: str,
        include: list[str] | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get a full overview of a managed device including compliance, users, and policies.

        USE: After finding a device_id with intune_search_devices. Call this first for full context.
        DON'T USE: When you only need hardware specs — use intune_get_device_hardware instead.

        Args:
            device_id: Intune managedDeviceId (GUID from search results).
            include: Sections to include — any of ["hardware","primaryUser","compliance","policies","detectedApps"].
                     Omit to include primaryUser and compliance (default).
        """
        try:
            result = await device_service.get_device_overview(device_id, include)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_device_hardware", annotations={**_ANNOTATIONS, "title": "Get Device Hardware"})
    @audited
    async def intune_get_device_hardware(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get hardware inventory for a managed device: model, serial number, storage, RAM.

        USE: When user asks about device specs, storage capacity, or hardware configuration.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_device_hardware(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_device_users", annotations={**_ANNOTATIONS, "title": "Get Device Users"})
    @audited
    async def intune_get_device_users(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get users associated with a managed device (primary user and logged-on users).

        USE: When user asks who owns a device or which users have logged on.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_device_users(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_detected_apps", annotations={**_ANNOTATIONS, "title": "Get Detected Apps"})
    @audited
    async def intune_get_detected_apps(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get all software detected on a managed device (full paginated list).

        USE: When user asks about installed apps, software inventory, or needs to verify if specific software is present.
        Note: May return hundreds of items — consider filtering by name client-side.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_detected_apps(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_compliance_state", annotations={**_ANNOTATIONS, "title": "Get Compliance State"})
    @audited
    async def intune_get_compliance_state(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get compliance state and list of failing compliance policies for a managed device.

        USE: When user asks 'why is this device non-compliant?' or needs compliance details.
        Returns device compliance summary AND per-policy states (compliant/nonCompliant/error).

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_compliance_state(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_policy_status", annotations={**_ANNOTATIONS, "title": "Get Policy Status"})
    @audited
    async def intune_get_policy_status(
        device_id: str,
        policy_type: str | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get configuration policy assignment states for a managed device.

        USE: When user asks 'which configuration policy is failing?', 'what policies are applied to this device?'.
        DON'T USE for compliance policies — use intune_get_compliance_state instead.

        Args:
            device_id: Intune managedDeviceId (GUID).
            policy_type: Optional platform type filter, e.g. 'windows10', 'iOS'.
        """
        try:
            result = await device_service.get_policy_status(device_id, policy_type)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tool_registration.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass (config, errors, auth, graph_client, utils, device_service, tool_registration).

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/tools/device/device_tools.py tests/test_tool_registration.py
git commit -m "feat: add device tools with MCP registration"
```

---

## Task 9: Server Wiring

**Files:**
- Create: `src/mcp_intune/server.py`

- [ ] **Step 1: Create src/mcp_intune/server.py**

```python
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import fastmcp
import structlog

from mcp_intune.graph.client import _http_client
from mcp_intune.logging_config import configure_logging
from mcp_intune.tools.device import device_tools

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def _lifespan(server: fastmcp.FastMCP) -> AsyncGenerator[None, None]:
    logger.info("server_starting", transport=os.getenv("FASTMCP_TRANSPORT", "http"))
    yield
    try:
        await _http_client.aclose()
    except Exception:
        pass
    logger.info("server_stopped")


mcp = fastmcp.FastMCP("mcp-intune", lifespan=_lifespan)
device_tools._register(mcp)


def main() -> None:
    transport = os.getenv("FASTMCP_TRANSPORT", "http")
    host = os.getenv("FASTMCP_HOST", "127.0.0.1")
    port = int(os.getenv("FASTMCP_PORT", "8000"))
    if transport == "http":
        mcp.run(transport=transport, host=host, port=port)
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Smoke test — start the server**

Copy `.env.example` to `.env` and fill in real Azure credentials, then:

```bash
python -m mcp_intune.server
```

Expected output:
```
{"event": "server_starting", "transport": "http", ...}
```

Then in another terminal:
```bash
curl -s http://127.0.0.1:8000/sse
```

Expected: SSE connection opens (streaming response headers).

- [ ] **Step 4: Verify tools list via MCP**

```bash
curl -s -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expected: JSON response listing 7 `intune_*` tools.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/server.py
git commit -m "feat: wire FastMCP server with device tools — V1 complete"
```

---

## Done

V1 delivers a running HTTP+SSE MCP server with 7 read-only Intune device tools backed by Microsoft Graph v1.0. Next: V2 adds remote actions (request_sync, request_restart) with approval workflow and beta-gated remediations.
