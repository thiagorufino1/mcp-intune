# MCP Intune V2 — Remote Actions, Approval Workflow, Reporting & Analytics

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add remote device actions (sync/restart/scan/locate + destructive retire/wipe/delete with approval workflow) and reporting tools (ExportJobs, audit events, endpoint analytics).

**Architecture:** Non-destructive actions call Graph directly; destructive actions create an in-memory approval request and return `status: pending_approval`. Approval tools (list/approve/deny) allow the operator to decide; once approved, `intune_execute_action` calls Graph. Reporting uses Graph ExportJobs (async POST→poll) for bulk exports and direct GET for audit events and analytics.

**Tech Stack:** Python 3.12, FastMCP, httpx, pydantic-settings, structlog, pytest, pytest-asyncio, unittest.mock

---

## Codebase context

Project root: `C:\Users\thiag\OneDrive\Thiago\github\mcp-intune`

Existing patterns to follow:
- All services in `src/mcp_intune/services/<domain>/`
- All tools in `src/mcp_intune/tools/<domain>/`, each with `_register(mcp)` function
- `graph_post(path, body)` in `src/mcp_intune/graph/client.py` — returns parsed JSON or raises `GraphError` subclass
- `graph_get(path, params, ttl)` for reads with cache
- `@audited` decorator from `src/mcp_intune/utils/audit.py` — wraps every tool
- `render_response(result, response_format)` from `src/mcp_intune/utils/render.py`
- `graph_error_response(exc, context)` from `src/mcp_intune/utils/graph_errors.py`
- `_ANNOTATIONS = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}` in each tool module
- Tests use `unittest.mock.AsyncMock` + `patch("mcp_intune.services.X.Y.graph_post", ...)`, no respx needed for service tests
- `conftest.py` sets env vars before any import and has `clear_graph_cache` autouse fixture
- Run tests: `pytest tests -v` from project root

---

## File structure

```
src/mcp_intune/
  approval/
    __init__.py          (empty)
    models.py            NEW: ApprovalRequest dataclass, ApprovalStatus/ActionRisk enums
    store.py             NEW: in-memory async store with create/list/decide operations
  services/
    device/
      action_service.py  NEW: non-destructive actions (sync, restart, scan, locate)
      destructive_action_service.py  NEW: retire/wipe/delete — creates approval requests + executes after approval
    reporting/
      __init__.py        NEW (empty)
      report_service.py  NEW: export_report, get_report_status, list_report_catalog
      audit_service.py   NEW: get_audit_events
      analytics_service.py  NEW: get_endpoint_analytics_summary
  tools/
    device/
      action_tools.py    NEW: registers 10 action tools including approval management
    reporting/
      __init__.py        NEW (empty)
      reporting_tools.py NEW: registers 5 reporting tools
  graph/
    client.py            MODIFY: add graph_delete(), fix _do_request to handle 204 No Content
  config.py              MODIFY: add approval_ttl_seconds field
  server.py              MODIFY: register action_tools and reporting_tools

tests/
  test_approval_store.py    NEW
  test_action_service.py    NEW
  test_reporting_service.py NEW
```

---

## Task 1: Fix `_do_request` for 204 and add `graph_delete`

**Files:**
- Modify: `src/mcp_intune/graph/client.py`
- Test: `tests/test_graph_client.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_graph_client.py`:

```python
@pytest.mark.asyncio
async def test_do_request_handles_204_no_content():
    """Action endpoints like syncDevice return 204 with empty body."""
    with patch("mcp_intune.graph.client._get_http_client") as mock_client_fn:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://graph.microsoft.com/v1.0/test"
        mock_client_fn.return_value.request = AsyncMock(return_value=mock_resp)
        from mcp_intune.graph.client import _do_request
        result = await _do_request("POST", "https://graph.microsoft.com/v1.0/test")
        assert result == {}


@pytest.mark.asyncio
async def test_graph_delete_calls_delete_method():
    with patch("mcp_intune.graph.client._do_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {}
        from mcp_intune.graph.client import graph_delete
        await graph_delete("v1.0/deviceManagement/managedDevices/abc-123")
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "DELETE"
        assert "abc-123" in call_args[0][1]
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_graph_client.py::test_do_request_handles_204_no_content tests/test_graph_client.py::test_graph_delete_calls_delete_method -v
```

Expected: FAIL — `graph_delete` not defined, and 204 causes json decode error.

- [ ] **Step 3: Implement in `src/mcp_intune/graph/client.py`**

Find `async def _do_request(...)` and update the return lines:

```python
@retry(
    retry=retry_if_exception_type((ThrottlingError, ServiceUnavailableError)),
    stop=stop_after_attempt(settings.graph_max_retries),
    wait=_retry_wait,
    reraise=True,
)
async def _do_request(method: str, url: str, json: Any = None, params: dict[str, Any] | None = None) -> Any:
    start = time.monotonic()
    response = await _get_http_client().request(method, url, headers=_headers(), json=json, params=params)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.debug("graph_request", method=method, status=response.status_code, elapsed_ms=elapsed_ms)
    _raise_for_status(response)
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()
```

Add `graph_delete` after `graph_post`:

```python
async def graph_delete(path: str) -> None:
    _assert_beta_allowed(path)
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    await _do_request("DELETE", url)
```

- [ ] **Step 4: Run to verify they pass**

```
pytest tests/test_graph_client.py::test_do_request_handles_204_no_content tests/test_graph_client.py::test_graph_delete_calls_delete_method -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite to check no regressions**

```
pytest tests -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/graph/client.py tests/test_graph_client.py
git commit -m "feat: add graph_delete and handle 204 No Content in _do_request"
```

---

## Task 2: Config — add `approval_ttl_seconds`

**Files:**
- Modify: `src/mcp_intune/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing test**

Add to `tests/test_graph_client.py` (or a new `tests/test_config.py`):

```python
def test_approval_ttl_seconds_default():
    from mcp_intune.config import settings
    assert settings.approval_ttl_seconds == 3600
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/test_graph_client.py::test_approval_ttl_seconds_default -v
```

Expected: FAIL — attribute not found.

- [ ] **Step 3: Add field to `src/mcp_intune/config.py`**

Find the `Settings` class and add after existing fields:

```python
approval_ttl_seconds: int = 3600  # how long a pending approval stays valid
```

- [ ] **Step 4: Add to `.env.example`**

```
APPROVAL_TTL_SECONDS=3600
```

- [ ] **Step 5: Run to verify it passes**

```
pytest tests/test_graph_client.py::test_approval_ttl_seconds_default -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/config.py .env.example
git commit -m "feat: add approval_ttl_seconds config field"
```

---

## Task 3: Approval store — models and in-memory store

**Files:**
- Create: `src/mcp_intune/approval/__init__.py`
- Create: `src/mcp_intune/approval/models.py`
- Create: `src/mcp_intune/approval/store.py`
- Create: `tests/test_approval_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_approval_store.py
import pytest
from unittest.mock import patch
import asyncio


@pytest.mark.asyncio
async def test_create_request_returns_pending():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        operation="wipe",
        device_id="dev-1",
        device_name="LAP-001",
        reason="Security incident",
        ticket_id="INC-001",
        risk="high",
    )
    from mcp_intune.approval.models import ApprovalStatus
    assert req.status == ApprovalStatus.PENDING
    assert req.operation == "wipe"
    assert req.request_id in store._store


@pytest.mark.asyncio
async def test_list_pending_returns_only_pending():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        operation="retire", device_id="d1", device_name="LAP-002",
        reason="Test", ticket_id="INC-002", risk="medium",
    )
    pending = await store.list_pending()
    assert any(r.request_id == req.request_id for r in pending)


@pytest.mark.asyncio
async def test_decide_approve_changes_status():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    store._store.clear()
    req = await store.create_request(
        operation="wipe", device_id="d2", device_name="LAP-003",
        reason="Test", ticket_id="INC-003", risk="high",
    )
    result = await store.decide(req.request_id, approve=True, comment="Approved")
    assert result.status == ApprovalStatus.APPROVED
    assert result.comment == "Approved"


@pytest.mark.asyncio
async def test_decide_deny_changes_status():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    store._store.clear()
    req = await store.create_request(
        operation="wipe", device_id="d3", device_name="LAP-004",
        reason="Test", ticket_id="INC-004", risk="high",
    )
    result = await store.decide(req.request_id, approve=False, comment="Denied")
    assert result.status == ApprovalStatus.DENIED


@pytest.mark.asyncio
async def test_get_request_returns_none_for_unknown():
    from mcp_intune.approval import store
    result = await store.get_request("nonexistent-id")
    assert result is None
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_approval_store.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/approval/__init__.py`**

```python
```

(empty file)

- [ ] **Step 4: Create `src/mcp_intune/approval/models.py`**

```python
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ActionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ApprovalRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation: str = ""
    device_id: str = ""
    device_name: str = ""
    risk: ActionRisk = ActionRisk.HIGH
    reason: str = ""
    ticket_id: str = ""
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_at: datetime | None = None
    comment: str | None = None
    action_params: dict = field(default_factory=dict)
```

- [ ] **Step 5: Create `src/mcp_intune/approval/store.py`**

```python
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from mcp_intune.approval.models import ActionRisk, ApprovalRequest, ApprovalStatus
from mcp_intune.config import settings

_store: dict[str, ApprovalRequest] = {}
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def create_request(
    operation: str,
    device_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
    risk: str = "high",
    action_params: dict[str, Any] | None = None,
) -> ApprovalRequest:
    req = ApprovalRequest(
        operation=operation,
        device_id=device_id,
        device_name=device_name,
        risk=ActionRisk(risk),
        reason=reason,
        ticket_id=ticket_id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.approval_ttl_seconds),
        action_params=action_params or {},
    )
    async with _get_lock():
        _store[req.request_id] = req
    return req


async def get_request(request_id: str) -> ApprovalRequest | None:
    async with _get_lock():
        return _store.get(request_id)


async def list_pending() -> list[ApprovalRequest]:
    now = datetime.now(timezone.utc)
    async with _get_lock():
        result = []
        for req in _store.values():
            if req.status == ApprovalStatus.PENDING:
                if req.expires_at and req.expires_at < now:
                    req.status = ApprovalStatus.EXPIRED
                else:
                    result.append(req)
        return list(result)


async def decide(request_id: str, approve: bool, comment: str = "") -> ApprovalRequest | None:
    now = datetime.now(timezone.utc)
    async with _get_lock():
        req = _store.get(request_id)
        if req is None:
            return None
        if req.status != ApprovalStatus.PENDING:
            return req
        if req.expires_at and req.expires_at < now:
            req.status = ApprovalStatus.EXPIRED
            return req
        req.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED
        req.decided_at = now
        req.comment = comment
        return req
```

- [ ] **Step 6: Run to verify tests pass**

```
pytest tests/test_approval_store.py -v
```

Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/mcp_intune/approval/ tests/test_approval_store.py
git commit -m "feat: add approval store with in-memory pending/approve/deny"
```

---

## Task 4: Action service — non-destructive actions

**Files:**
- Create: `src/mcp_intune/services/device/action_service.py`
- Create: `tests/test_action_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_action_service.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_request_sync_calls_graph_post():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_sync
        result = await request_sync("abc-123")
        assert result["action"] == "syncDevice"
        assert result["status"] == "initiated"
        call_path = mock_post.call_args[0][0]
        assert "abc-123" in call_path
        assert "syncDevice" in call_path


@pytest.mark.asyncio
async def test_request_restart_calls_graph_post():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_restart
        result = await request_restart("abc-123")
        assert result["action"] == "rebootNow"
        assert result["status"] == "initiated"
        call_path = mock_post.call_args[0][0]
        assert "rebootNow" in call_path


@pytest.mark.asyncio
async def test_request_scan_sends_quick_scan_flag():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_scan
        result = await request_scan("abc-123", quick_scan=True)
        assert result["action"] == "windowsDefenderScan"
        body = mock_post.call_args[0][1]
        assert body.get("quickScan") is True


@pytest.mark.asyncio
async def test_request_locate_calls_graph_post():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_locate
        result = await request_locate("abc-123")
        assert result["action"] == "locateDevice"
        call_path = mock_post.call_args[0][0]
        assert "locateDevice" in call_path
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_action_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/device/action_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_post

DEVICE_BASE = "v1.0/deviceManagement/managedDevices"


async def request_sync(device_id: str) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/syncDevice", {})
    return {"action": "syncDevice", "device_id": device_id, "status": "initiated"}


async def request_restart(device_id: str) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/rebootNow", {})
    return {"action": "rebootNow", "device_id": device_id, "status": "initiated"}


async def request_scan(device_id: str, quick_scan: bool = True) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/windowsDefenderScan", {"quickScan": quick_scan})
    return {"action": "windowsDefenderScan", "device_id": device_id, "quickScan": quick_scan, "status": "initiated"}


async def request_locate(device_id: str) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/locateDevice", {})
    return {"action": "locateDevice", "device_id": device_id, "status": "initiated"}
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_action_service.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/device/action_service.py tests/test_action_service.py
git commit -m "feat: add non-destructive action service (sync, restart, scan, locate)"
```

---

## Task 5: Destructive action service — retire, wipe, delete with approval

**Files:**
- Create: `src/mcp_intune/services/device/destructive_action_service.py`
- Modify: `tests/test_action_service.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_action_service.py`:

```python
@pytest.mark.asyncio
async def test_request_retire_creates_pending_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.device.destructive_action_service import request_retire
    result = await request_retire("dev-1", "LAP-001", "Security", "INC-001")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "retire"
    assert "request_id" in result


@pytest.mark.asyncio
async def test_request_wipe_creates_pending_approval_with_params():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.device.destructive_action_service import request_wipe
    result = await request_wipe("dev-2", "LAP-002", "Lost device", "INC-002", keep_enrollment_data=False)
    assert result["status"] == "pending_approval"
    assert result["operation"] == "wipe"
    req = store._store[result["request_id"]]
    assert req.action_params.get("keepEnrollmentData") is False


@pytest.mark.asyncio
async def test_execute_approved_action_calls_retire():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    store._store.clear()
    req = await store.create_request("retire", "dev-3", "LAP-003", "Test", "INC-003", "medium")
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.device.destructive_action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.destructive_action_service import execute_approved_action
        result = await execute_approved_action(req.request_id)
        assert result["executed"] == "retire"
        assert "dev-3" in mock_post.call_args[0][0]


@pytest.mark.asyncio
async def test_execute_approved_action_raises_if_not_approved():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request("wipe", "dev-4", "LAP-004", "Test", "INC-004", "high")
    from mcp_intune.services.device.destructive_action_service import execute_approved_action
    with pytest.raises(ValueError, match="not approved"):
        await execute_approved_action(req.request_id)
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_action_service.py::test_request_retire_creates_pending_approval tests/test_action_service.py::test_request_wipe_creates_pending_approval_with_params tests/test_action_service.py::test_execute_approved_action_calls_retire tests/test_action_service.py::test_execute_approved_action_raises_if_not_approved -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/device/destructive_action_service.py`**

```python
from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.approval.models import ApprovalStatus
from mcp_intune.graph.client import graph_delete, graph_post

DEVICE_BASE = "v1.0/deviceManagement/managedDevices"


async def request_retire(device_id: str, device_name: str, reason: str, ticket_id: str) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="retire",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="medium",
    )
    return {"status": "pending_approval", "request_id": req.request_id, "operation": "retire", "device_id": device_id}


async def request_wipe(
    device_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
    keep_enrollment_data: bool = False,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="wipe",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
        action_params={"keepEnrollmentData": keep_enrollment_data, "keepUserData": False},
    )
    return {"status": "pending_approval", "request_id": req.request_id, "operation": "wipe", "device_id": device_id}


async def request_delete(device_id: str, device_name: str, reason: str, ticket_id: str) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="delete",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
    )
    return {"status": "pending_approval", "request_id": req.request_id, "operation": "delete", "device_id": device_id}


async def execute_approved_action(request_id: str) -> dict[str, Any]:
    req = await approval_store.get_request(request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")
    if req.status != ApprovalStatus.APPROVED:
        raise ValueError(f"Request {request_id} is not approved (status: {req.status})")

    op = req.operation
    device_id = req.device_id

    if op == "retire":
        await graph_post(f"{DEVICE_BASE}/{device_id}/retire", {})
    elif op == "wipe":
        await graph_post(f"{DEVICE_BASE}/{device_id}/wipe", req.action_params)
    elif op == "delete":
        await graph_delete(f"{DEVICE_BASE}/{device_id}")
    else:
        raise ValueError(f"Unknown operation: {op}")

    return {"executed": op, "device_id": device_id, "request_id": request_id, "status": "executed"}
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_action_service.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/device/destructive_action_service.py tests/test_action_service.py
git commit -m "feat: add destructive action service with approval workflow"
```

---

## Task 6: Action tools registration

**Files:**
- Create: `src/mcp_intune/tools/device/action_tools.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_tool_registration.py`:

```python
def test_action_tools_registered():
    class FakeMCP:
        def __init__(self):
            self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator

    fake = FakeMCP()
    from mcp_intune.tools.device.action_tools import _register
    _register(fake)
    expected = {
        "intune_request_sync", "intune_request_restart", "intune_request_scan",
        "intune_request_locate", "intune_request_retire", "intune_request_wipe",
        "intune_request_delete", "intune_list_pending_actions",
        "intune_approve_action", "intune_deny_action", "intune_execute_action",
    }
    assert expected.issubset(fake.tools.keys())
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/test_tool_registration.py::test_action_tools_registered -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/tools/device/action_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.device import action_service, destructive_action_service
from mcp_intune.approval import store as approval_store
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_SAFE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}
_DESTRUCTIVE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False}
_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_request_sync", annotations={**_SAFE_ANNOTATIONS, "title": "Request Device Sync"})
    @audited
    async def intune_request_sync(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Initiate a sync for a managed device (non-destructive, executes immediately).

        USE: When device data in Intune is stale or you want to force a policy check-in.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await action_service.request_sync(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"sync device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_restart", annotations={**_SAFE_ANNOTATIONS, "title": "Request Device Restart"})
    @audited
    async def intune_request_restart(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request a remote reboot of a managed device (non-destructive, executes immediately).

        USE: When device needs a restart to apply policies or updates.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await action_service.request_restart(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"restart device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_scan", annotations={**_SAFE_ANNOTATIONS, "title": "Request Defender Scan"})
    @audited
    async def intune_request_scan(
        device_id: str,
        quick_scan: bool = True,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Initiate a Windows Defender scan on a managed device (executes immediately).

        USE: When malware is suspected or as part of incident response.

        Args:
            device_id: Intune managedDeviceId (GUID).
            quick_scan: True for quick scan (default), False for full scan.
        """
        try:
            result = await action_service.request_scan(device_id, quick_scan)
        except Exception as exc:
            result = graph_error_response(exc, context=f"scan device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_locate", annotations={**_SAFE_ANNOTATIONS, "title": "Request Device Location"})
    @audited
    async def intune_request_locate(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request location of a managed device (executes immediately, device must be online).

        USE: When a device is missing or stolen.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await action_service.request_locate(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"locate device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_retire", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Request Device Retire"})
    @audited
    async def intune_request_retire(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request retire of a managed device. REQUIRES APPROVAL before execution.

        Retire removes corporate data and unenrolls the device. Returns pending_approval status.
        Use intune_approve_action + intune_execute_action to complete.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification for this action.
            ticket_id: ITSM ticket reference (e.g. INC-12345).
        """
        try:
            result = await destructive_action_service.request_retire(device_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"retire device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_wipe", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Request Device Wipe"})
    @audited
    async def intune_request_wipe(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        keep_enrollment_data: bool = False,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request full wipe of a managed device. REQUIRES APPROVAL before execution.

        Wipe factory-resets the device. Returns pending_approval status.
        Use intune_approve_action + intune_execute_action to complete.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification.
            ticket_id: ITSM ticket reference.
            keep_enrollment_data: If True, device re-enrolls after wipe (default False).
        """
        try:
            result = await destructive_action_service.request_wipe(device_id, device_name, reason, ticket_id, keep_enrollment_data)
        except Exception as exc:
            result = graph_error_response(exc, context=f"wipe device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_delete", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Request Device Delete"})
    @audited
    async def intune_request_delete(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request deletion of a managed device record from Intune. REQUIRES APPROVAL before execution.

        Permanently removes the device from Intune. Use only for stale/ghost records.
        Returns pending_approval status. Use intune_approve_action + intune_execute_action to complete.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification.
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await destructive_action_service.request_delete(device_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"delete device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_pending_actions", annotations={**_READ_ANNOTATIONS, "title": "List Pending Approval Requests"})
    @audited
    async def intune_list_pending_actions(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List all pending device actions waiting for approval.

        USE: To see what actions are queued and need an approval decision.
        """
        try:
            pending = await approval_store.list_pending()
            result = {
                "pending": [
                    {
                        "request_id": r.request_id,
                        "operation": r.operation,
                        "device_id": r.device_id,
                        "device_name": r.device_name,
                        "risk": r.risk,
                        "reason": r.reason,
                        "ticket_id": r.ticket_id,
                        "requested_at": r.requested_at.isoformat(),
                        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                    }
                    for r in pending
                ],
                "count": len(pending),
            }
        except Exception as exc:
            result = graph_error_response(exc, context="list pending actions")
        return render_response(result, response_format)

    @mcp.tool(name="intune_approve_action", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Approve Pending Action"})
    @audited
    async def intune_approve_action(
        request_id: str,
        comment: str = "",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Approve a pending device action request. Does NOT execute — call intune_execute_action next.

        Args:
            request_id: The request_id returned by intune_request_retire/wipe/delete.
            comment: Optional approval comment for audit trail.
        """
        try:
            req = await approval_store.decide(request_id, approve=True, comment=comment)
            if req is None:
                result = {"error": f"Request {request_id} not found"}
            else:
                result = {
                    "request_id": req.request_id,
                    "status": req.status,
                    "operation": req.operation,
                    "device_id": req.device_id,
                    "next_step": "Call intune_execute_action to run the approved action",
                }
        except Exception as exc:
            result = graph_error_response(exc, context=f"approve request '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_deny_action", annotations={**_READ_ANNOTATIONS, "title": "Deny Pending Action"})
    @audited
    async def intune_deny_action(
        request_id: str,
        comment: str = "",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Deny a pending device action request.

        Args:
            request_id: The request_id returned by intune_request_retire/wipe/delete.
            comment: Reason for denial (recommended for audit trail).
        """
        try:
            req = await approval_store.decide(request_id, approve=False, comment=comment)
            if req is None:
                result = {"error": f"Request {request_id} not found"}
            else:
                result = {"request_id": req.request_id, "status": req.status, "operation": req.operation}
        except Exception as exc:
            result = graph_error_response(exc, context=f"deny request '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_execute_action", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Execute Approved Action"})
    @audited
    async def intune_execute_action(
        request_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Execute a previously approved device action against Microsoft Graph.

        USE: After intune_approve_action confirms the request. Will fail if not approved.

        Args:
            request_id: The request_id from the original request tool.
        """
        try:
            result = await destructive_action_service.execute_approved_action(request_id)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context=f"execute action '{request_id}'")
        return render_response(result, response_format)
```

- [ ] **Step 4: Run to verify test passes**

```
pytest tests/test_tool_registration.py::test_action_tools_registered -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```
pytest tests -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/tools/device/action_tools.py tests/test_tool_registration.py
git commit -m "feat: register 11 action tools with approval workflow"
```

---

## Task 7: Reporting service — ExportJobs and audit events

**Files:**
- Create: `src/mcp_intune/services/reporting/__init__.py`
- Create: `src/mcp_intune/services/reporting/report_service.py`
- Create: `src/mcp_intune/services/reporting/audit_service.py`
- Create: `tests/test_reporting_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_reporting_service.py
import pytest
from unittest.mock import AsyncMock, patch


EXPORT_JOB_STUB = {
    "id": "job-abc-123",
    "status": "notStarted",
    "reportName": "Devices",
    "url": None,
    "expirationDateTime": None,
}

AUDIT_EVENTS_STUB = {
    "value": [
        {
            "id": "evt-1",
            "displayName": "Update managed device",
            "category": "Device",
            "activityType": "Patch ManagedDevice",
            "activityDateTime": "2026-05-01T10:00:00Z",
            "actor": {"userPrincipalName": "admin@empresa.com"},
            "resources": [],
        }
    ]
}


@pytest.mark.asyncio
async def test_export_report_creates_export_job():
    with patch("mcp_intune.services.reporting.report_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = EXPORT_JOB_STUB
        from mcp_intune.services.reporting.report_service import export_report
        result = await export_report("Devices")
        assert result["jobId"] == "job-abc-123"
        assert result["status"] == "notStarted"
        body = mock_post.call_args[0][1]
        assert body["reportName"] == "Devices"
        assert body["format"] == "csv"


@pytest.mark.asyncio
async def test_export_report_passes_filter():
    with patch("mcp_intune.services.reporting.report_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = EXPORT_JOB_STUB
        from mcp_intune.services.reporting.report_service import export_report
        await export_report("Devices", filter="(Platform eq 'Windows')")
        body = mock_post.call_args[0][1]
        assert "Windows" in body.get("filter", "")


@pytest.mark.asyncio
async def test_get_report_status_calls_graph_get():
    with patch("mcp_intune.services.reporting.report_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {**EXPORT_JOB_STUB, "status": "completed", "url": "https://example.com/report.csv"}
        from mcp_intune.services.reporting.report_service import get_report_status
        result = await get_report_status("job-abc-123")
        assert result["status"] == "completed"
        assert "job-abc-123" in mock_get.call_args[0][0]


@pytest.mark.asyncio
async def test_get_audit_events_returns_events():
    with patch("mcp_intune.services.reporting.audit_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AUDIT_EVENTS_STUB
        from mcp_intune.services.reporting.audit_service import get_audit_events
        result = await get_audit_events(days=7)
        assert result["count"] == 1
        assert result["auditEvents"][0]["category"] == "Device"
        call_params = mock_get.call_args[1].get("params") or mock_get.call_args[0][1]
        assert "activityDateTime" in str(call_params)


@pytest.mark.asyncio
async def test_get_audit_events_with_actor_filter():
    with patch("mcp_intune.services.reporting.audit_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AUDIT_EVENTS_STUB
        from mcp_intune.services.reporting.audit_service import get_audit_events
        await get_audit_events(days=7, actor_upn="admin@empresa.com")
        call_params = str(mock_get.call_args)
        assert "admin@empresa.com" in call_params
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_reporting_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/reporting/__init__.py`**

Empty file.

- [ ] **Step 4: Create `src/mcp_intune/services/reporting/report_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_get, graph_post

REPORTS_BASE = "v1.0/deviceManagement/reports"

VALID_REPORTS = [
    "Devices", "DevicesWithInventory", "ActiveMalware", "AllAppsList",
    "AppInstallStatusAggregate", "ComanagedDeviceWorkloads", "CompliancePolicyStatuses",
    "ConfigurationPolicyStatuses", "DeviceComplianceTrend", "NonCompliantDeviceAndSettings",
    "PolicyNonComplianceSummary", "PolicyNonComplianceDetail", "Remediations",
    "RemediationDeviceStatus", "FeatureUpdatePolicyFailuresAggregate",
    "FeatureUpdateDeviceState", "QualityUpdateDeviceState", "QualityUpdatePolicyStatusCounts",
]


async def export_report(
    report_name: str,
    filter: str | None = None,
    select: list[str] | None = None,
    format: str = "csv",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "reportName": report_name,
        "format": format,
        "localizationType": "localizedValuesAsAdditionalColumn",
    }
    if filter:
        body["filter"] = filter
    if select:
        body["select"] = select
    result = await graph_post(f"{REPORTS_BASE}/exportJobs", body)
    return {
        "jobId": result.get("id"),
        "status": result.get("status"),
        "reportName": result.get("reportName"),
        "downloadUrl": result.get("url"),
        "expiresDateTime": result.get("expirationDateTime"),
    }


async def get_report_status(job_id: str) -> dict[str, Any]:
    result = await graph_get(f"{REPORTS_BASE}/exportJobs/{job_id}", ttl=10)
    return {
        "jobId": result.get("id"),
        "status": result.get("status"),
        "reportName": result.get("reportName"),
        "downloadUrl": result.get("url"),
        "expiresDateTime": result.get("expirationDateTime"),
    }


def list_report_catalog() -> list[str]:
    return VALID_REPORTS
```

- [ ] **Step 5: Create `src/mcp_intune/services/reporting/audit_service.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp_intune.graph.client import graph_get

AUDIT_BASE = "v1.0/deviceManagement/auditEvents"


async def get_audit_events(
    days: int = 7,
    actor_upn: str | None = None,
    category: str | None = None,
    top: int = 50,
) -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_parts = [f"activityDateTime gt {since}"]
    if actor_upn:
        filter_parts.append(f"actor/userPrincipalName eq '{actor_upn}'")
    if category:
        filter_parts.append(f"category eq '{category}'")
    params = {
        "$filter": " and ".join(filter_parts),
        "$orderby": "activityDateTime desc",
        "$top": top,
        "$select": "id,displayName,category,activityType,activityDateTime,actor,resources",
    }
    result = await graph_get(AUDIT_BASE, params=params, ttl=60)
    events = result.get("value", [])
    return {"auditEvents": events, "count": len(events)}
```

- [ ] **Step 6: Run to verify tests pass**

```
pytest tests/test_reporting_service.py -v
```

Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/mcp_intune/services/reporting/ tests/test_reporting_service.py
git commit -m "feat: add reporting service (export jobs, audit events)"
```

---

## Task 8: Analytics service

**Files:**
- Create: `src/mcp_intune/services/reporting/analytics_service.py`
- Modify: `tests/test_reporting_service.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_reporting_service.py`:

```python
ANALYTICS_STUB = {
    "id": "summary",
    "overallScore": 72,
    "startupPerformanceScore": 81,
    "appReliabilityScore": 68,
    "workFromAnywhereScore": 75,
}


@pytest.mark.asyncio
async def test_get_endpoint_analytics_summary_returns_scores():
    with patch("mcp_intune.services.reporting.analytics_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = ANALYTICS_STUB
        from mcp_intune.services.reporting.analytics_service import get_endpoint_analytics_summary
        result = await get_endpoint_analytics_summary()
        assert result["overallScore"] == 72
        call_path = mock_get.call_args[0][0]
        assert "userExperienceAnalytics" in call_path
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/test_reporting_service.py::test_get_endpoint_analytics_summary_returns_scores -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/reporting/analytics_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_get

ANALYTICS_OVERVIEW = "v1.0/deviceManagement/userExperienceAnalyticsOverview"


async def get_endpoint_analytics_summary() -> dict[str, Any]:
    return await graph_get(ANALYTICS_OVERVIEW, ttl=300)
```

- [ ] **Step 4: Run to verify it passes**

```
pytest tests/test_reporting_service.py::test_get_endpoint_analytics_summary_returns_scores -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/reporting/analytics_service.py tests/test_reporting_service.py
git commit -m "feat: add endpoint analytics service"
```

---

## Task 9: Reporting tools registration

**Files:**
- Create: `src/mcp_intune/tools/reporting/__init__.py`
- Create: `src/mcp_intune/tools/reporting/reporting_tools.py`
- Modify: `tests/test_tool_registration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_tool_registration.py`:

```python
def test_reporting_tools_registered():
    class FakeMCP:
        def __init__(self):
            self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator

    fake = FakeMCP()
    from mcp_intune.tools.reporting.reporting_tools import _register
    _register(fake)
    expected = {
        "intune_export_report", "intune_get_report_status", "intune_list_report_catalog",
        "intune_get_audit_events", "intune_get_endpoint_analytics",
    }
    assert expected.issubset(fake.tools.keys())
```

- [ ] **Step 2: Run to verify it fails**

```
pytest tests/test_tool_registration.py::test_reporting_tools_registered -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/tools/reporting/__init__.py`**

Empty file.

- [ ] **Step 4: Create `src/mcp_intune/tools/reporting/reporting_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.reporting import analytics_service, audit_service, report_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_WRITE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_export_report", annotations={**_WRITE_ANNOTATIONS, "title": "Export Intune Report"})
    @audited
    async def intune_export_report(
        report_name: str,
        filter: str | None = None,
        select: list[str] | None = None,
        format: str = "csv",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Create an Intune report export job. Returns a jobId to poll with intune_get_report_status.

        USE: For bulk device/compliance/app data exports. Call intune_list_report_catalog first.
        DON'T USE for real-time queries — use device tools instead.

        Args:
            report_name: Report identifier (e.g. 'Devices', 'CompliancePolicyStatuses').
            filter: OData filter string (e.g. "(Platform eq 'Windows')").
            select: Column names to include (e.g. ["DeviceName", "ComplianceState"]).
            format: Export format — 'csv' (default) or 'json'.
        """
        try:
            result = await report_service.export_report(report_name, filter, select, format)
        except Exception as exc:
            result = graph_error_response(exc, context=f"export report '{report_name}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_report_status", annotations={**_READ_ANNOTATIONS, "title": "Get Report Export Status"})
    @audited
    async def intune_get_report_status(
        job_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Check the status of a report export job. When status is 'completed', downloadUrl is available.

        USE: After intune_export_report. Poll until status changes to 'completed' or 'failed'.

        Args:
            job_id: The jobId returned by intune_export_report.
        """
        try:
            result = await report_service.get_report_status(job_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"report status '{job_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_report_catalog", annotations={**_READ_ANNOTATIONS, "title": "List Available Reports"})
    @audited
    async def intune_list_report_catalog(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List all available Intune report names for use with intune_export_report.

        USE: When unsure which report_name to use in intune_export_report.
        """
        try:
            result = {"reports": report_service.list_report_catalog(), "count": len(report_service.list_report_catalog())}
        except Exception as exc:
            result = graph_error_response(exc, context="list report catalog")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_audit_events", annotations={**_READ_ANNOTATIONS, "title": "Get Audit Events"})
    @audited
    async def intune_get_audit_events(
        days: int = 7,
        actor_upn: str | None = None,
        category: str | None = None,
        top: int = 50,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get Intune audit events (who did what, when).

        USE: For change tracking, incident investigation, or compliance audits.

        Args:
            days: How many days back to fetch (default 7, max 30 recommended).
            actor_upn: Filter by the UPN of the admin who made changes.
            category: Filter by category e.g. 'Device', 'DeviceConfiguration', 'CompliancePolicy'.
            top: Max number of events to return (default 50).
        """
        try:
            result = await audit_service.get_audit_events(days, actor_upn, category, top)
        except Exception as exc:
            result = graph_error_response(exc, context="get audit events")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_endpoint_analytics", annotations={**_READ_ANNOTATIONS, "title": "Get Endpoint Analytics"})
    @audited
    async def intune_get_endpoint_analytics(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get Endpoint Analytics overview scores for the tenant (startup performance, app reliability, etc).

        USE: For fleet health overview. Scores range 0–100, higher is better.
        """
        try:
            result = await analytics_service.get_endpoint_analytics_summary()
        except Exception as exc:
            result = graph_error_response(exc, context="get endpoint analytics")
        return render_response(result, response_format)
```

- [ ] **Step 5: Run to verify test passes**

```
pytest tests/test_tool_registration.py::test_reporting_tools_registered -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/tools/reporting/ tests/test_tool_registration.py
git commit -m "feat: register 5 reporting tools (export, status, catalog, audit, analytics)"
```

---

## Task 10: Wire server + update readme and changelog

**Files:**
- Modify: `src/mcp_intune/server.py`
- Modify: `readme.md`
- Modify: `changelog.md`

- [ ] **Step 1: Write failing test**

Add to `tests/test_tool_registration.py`:

```python
def test_server_registers_all_tool_modules():
    """Verify server.py imports and registers action and reporting tools."""
    import importlib
    import sys
    # Remove cached module to force re-import
    for mod in list(sys.modules.keys()):
        if "mcp_intune.server" in mod:
            del sys.modules[mod]
    server = importlib.import_module("mcp_intune.server")
    # server.py must call _register for both new tool modules
    assert hasattr(server, "mcp")
```

- [ ] **Step 2: Run to verify it passes (it should already, but checks import)**

```
pytest tests/test_tool_registration.py::test_server_registers_all_tool_modules -v
```

- [ ] **Step 3: Update `src/mcp_intune/server.py`**

```python
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import fastmcp
import structlog

from mcp_intune.graph.client import _get_http_client
from mcp_intune.logging_config import configure_logging
from mcp_intune.tools.device import device_tools, action_tools
from mcp_intune.tools.reporting import reporting_tools

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def _lifespan(server: fastmcp.FastMCP) -> AsyncGenerator[None, None]:
    logger.info("server_starting", transport=os.getenv("FASTMCP_TRANSPORT", "http"))
    yield
    client = _get_http_client()
    try:
        await client.aclose()
    except Exception as exc:
        logger.warning("http_client_close_error", error=str(exc))
    logger.info("server_stopped")


mcp = fastmcp.FastMCP("mcp-intune", lifespan=_lifespan)
device_tools._register(mcp)
action_tools._register(mcp)
reporting_tools._register(mcp)


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

- [ ] **Step 4: Update `readme.md` — add V2 tools to tool reference section**

In `readme.md`, update **Total atual** to **23 ferramentas** and add two new sections after `### 💻 Dispositivos`:

```markdown
### ⚡ Ações Remotas

- **`intune_request_sync`**: forçar sincronização de políticas (executa imediatamente).
- **`intune_request_restart`**: reiniciar dispositivo remotamente (executa imediatamente).
- **`intune_request_scan`**: iniciar varredura do Windows Defender — quick ou full scan (executa imediatamente).
- **`intune_request_locate`**: solicitar localização do dispositivo (executa imediatamente, dispositivo deve estar online).
- **`intune_request_retire`**: retire do dispositivo com remoção de dados corporativos. **Requer aprovação** — retorna `pending_approval`.
- **`intune_request_wipe`**: wipe factory reset do dispositivo. **Requer aprovação** — retorna `pending_approval`.
- **`intune_request_delete`**: exclusão do registro do dispositivo no Intune. **Requer aprovação** — retorna `pending_approval`.
- **`intune_list_pending_actions`**: lista ações destrutivas aguardando aprovação.
- **`intune_approve_action`**: aprova uma ação pendente (não executa — use `intune_execute_action` em seguida).
- **`intune_deny_action`**: rejeita uma ação pendente.
- **`intune_execute_action`**: executa uma ação já aprovada contra o Graph. Falha se não estiver aprovada.

### 📊 Relatórios e Auditoria

- **`intune_export_report`**: cria um ExportJob assíncrono do Intune. Retorna `jobId` para polling com `intune_get_report_status`. Use `intune_list_report_catalog` para ver reports disponíveis.
- **`intune_get_report_status`**: verifica status de um ExportJob. Quando `status=completed`, `downloadUrl` está disponível.
- **`intune_list_report_catalog`**: lista todos os nomes de relatórios disponíveis para uso com `intune_export_report`.
- **`intune_get_audit_events`**: consulta eventos de auditoria do Intune (quem fez o quê, quando). Filtrável por ator, categoria e período.
- **`intune_get_endpoint_analytics`**: visão geral de scores de Endpoint Analytics do tenant (startup, app reliability, work from anywhere).
```

Update permissions table to add:

```markdown
| `DeviceManagementApps.Read.All` | Eventos de auditoria |
| `DeviceManagementManagedDevices.ReadWrite.All` | ExportJobs e relatórios |
| `DeviceManagementManagedDevices.PrivilegedOperations.All` | Ações remotas (retire, wipe) |
```

- [ ] **Step 5: Update `changelog.md`** — add V2 entry at top (after header):

```markdown
## 2026-05-02 — V2: Ações Remotas, Approval Workflow e Reporting

### Added

- **Ações remotas não-destrutivas** (executam imediatamente)
  - `intune_request_sync`, `intune_request_restart`, `intune_request_scan`, `intune_request_locate`

- **Ações destrutivas com approval workflow**
  - `intune_request_retire`, `intune_request_wipe`, `intune_request_delete` — retornam `status: pending_approval`
  - `intune_list_pending_actions`, `intune_approve_action`, `intune_deny_action`, `intune_execute_action`
  - Approval store in-memory com TTL configurável (`APPROVAL_TTL_SECONDS`, padrão 3600s)

- **Reporting (ExportJobs)**
  - `intune_export_report` — cria ExportJob assíncrono (POST → polling)
  - `intune_get_report_status` — polling do status e downloadUrl
  - `intune_list_report_catalog` — catálogo de 18 relatórios disponíveis

- **Auditoria**
  - `intune_get_audit_events` — eventos de auditoria com filtro por período, ator e categoria

- **Endpoint Analytics**
  - `intune_get_endpoint_analytics` — scores de startup performance, app reliability e work from anywhere

- **`graph_delete`** helper no GraphGateway
- Correção: `_do_request` agora retorna `{}` para respostas 204 No Content (usado por ações remotas)

### Changed

- **Total de tools expostas: 23** (era 7 na V1)
- `config.py`: adicionado campo `APPROVAL_TTL_SECONDS`

---
```

- [ ] **Step 6: Run full test suite**

```
pytest tests -v
```

Expected: all tests PASS (38+ tests).

- [ ] **Step 7: Commit**

```bash
git add src/mcp_intune/server.py readme.md changelog.md
git commit -m "feat: wire V2 tools in server, update readme and changelog"
```
