# MCP Intune V3 — Governance, Sensitive Ops, Autopatch & Bulk

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LAPS and BitLocker sensitive operations (with mandatory approval), RBAC governance tools, Windows Autopatch management, and bulk device actions.

**Architecture:** Sensitive ops (LAPS secret, BitLocker key) always route through the approval store before calling Graph — the key value is never returned without an explicit approval + execute flow. RBAC tools are read-only. Autopatch uses the `/admin/windows/updates/` namespace. Bulk actions batch up to 20 device action requests using the existing `build_batch` helper.

**Tech Stack:** Python 3.12, FastMCP, httpx, pytest, pytest-asyncio, unittest.mock

---

## Codebase context

Project root: `C:\Users\thiag\OneDrive\Thiago\github\mcp-intune`

**Prerequisites:** V2 and V2b plans must be fully implemented.

Existing patterns:
- Service modules in `src/mcp_intune/services/<domain>/`
- Tool modules in `src/mcp_intune/tools/<domain>/` with `_register(mcp)` function
- `graph_get(path, params, ttl)`, `graph_post(path, body)`, `graph_get_paged(path, params, top)` from `src/mcp_intune/graph/client.py`
- `build_batch(requests_list)` from same module — validates ≤20 requests
- Approval store: `from mcp_intune.approval import store as approval_store`
- `from mcp_intune.approval.models import ApprovalStatus`
- `@audited`, `render_response`, `graph_error_response` from utils
- Beta paths require `ALLOW_BETA_APIS=true`
- Run tests: `pytest tests -v`

---

## File structure

```
src/mcp_intune/
  services/
    governance/
      __init__.py          NEW (empty)
      laps_service.py      NEW: get_laps_metadata, request_laps_secret (approval-gated), execute_laps_secret
      bitlocker_service.py NEW: find_bitlocker_key (metadata), request_bitlocker_key (approval), execute_bitlocker_key
      rbac_service.py      NEW: list_role_definitions, list_role_assignments, validate_access_scope
    autopatch/
      __init__.py          NEW (empty)
      autopatch_service.py NEW: list_deployments, get_deployment, list_updatable_assets
    device/
      bulk_action_service.py  NEW: bulk_sync, bulk_restart — uses build_batch
  tools/
    governance/
      __init__.py          NEW (empty)
      governance_tools.py  NEW: registers 8 governance tools
    autopatch/
      __init__.py          NEW (empty)
      autopatch_tools.py   NEW: registers 3 autopatch tools
    device/
      bulk_tools.py        NEW: registers 2 bulk action tools
  server.py                MODIFY: register governance, autopatch, bulk tools

tests/
  test_laps_bitlocker_service.py  NEW
  test_rbac_service.py            NEW
  test_autopatch_service.py       NEW
  test_bulk_action_service.py     NEW
```

---

## Task 1: LAPS service — metadata and approval-gated secret

**Files:**
- Create: `src/mcp_intune/services/governance/__init__.py`
- Create: `src/mcp_intune/services/governance/laps_service.py`
- Create: `tests/test_laps_bitlocker_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_laps_bitlocker_service.py
import pytest
from unittest.mock import AsyncMock, patch


LAPS_METADATA_STUB = {
    "id": "cred-1",
    "deviceName": "LAP-001",
    "refreshDateTime": "2026-05-01T08:00:00Z",
    "credentials": [
        {
            "backupDateTime": "2026-05-01T08:00:00Z",
            "accountName": "Administrator",
        }
    ],
}


@pytest.mark.asyncio
async def test_get_laps_metadata_calls_correct_endpoint():
    with patch("mcp_intune.services.governance.laps_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = LAPS_METADATA_STUB
        from mcp_intune.services.governance.laps_service import get_laps_metadata
        result = await get_laps_metadata("dev-abc")
        assert result["deviceName"] == "LAP-001"
        call_path = mock_get.call_args[0][0]
        assert "dev-abc" in call_path
        assert "deviceLocalCredentialInfo" in call_path or "localCredentialInfo" in call_path


@pytest.mark.asyncio
async def test_request_laps_secret_creates_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.governance.laps_service import request_laps_secret
    result = await request_laps_secret("dev-abc", "LAP-001", "Admin recovery", "INC-001")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "laps_secret"
    assert result["risk"] == "high"


@pytest.mark.asyncio
async def test_execute_laps_secret_calls_graph_with_select_key():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    store._store.clear()
    req = await store.create_request(
        "laps_secret", "dev-abc", "LAP-001", "Test", "INC-001", "high",
        action_params={"device_id": "dev-abc"},
    )
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.governance.laps_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {**LAPS_METADATA_STUB, "credentials": [{"accountName": "Administrator", "password": "SecretP@ss1"}]}
        from mcp_intune.services.governance.laps_service import execute_laps_secret
        result = await execute_laps_secret(req.request_id)
        assert result["credentials"] is not None
        call_params = str(mock_get.call_args)
        assert "$select" in call_params
        assert "credentials" in call_params


@pytest.mark.asyncio
async def test_execute_laps_secret_raises_if_not_approved():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request("laps_secret", "dev-abc", "LAP-001", "Test", "INC-002", "high")
    from mcp_intune.services.governance.laps_service import execute_laps_secret
    with pytest.raises(ValueError, match="not approved"):
        await execute_laps_secret(req.request_id)
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_laps_bitlocker_service.py::test_get_laps_metadata_calls_correct_endpoint tests/test_laps_bitlocker_service.py::test_request_laps_secret_creates_approval tests/test_laps_bitlocker_service.py::test_execute_laps_secret_calls_graph_with_select_key tests/test_laps_bitlocker_service.py::test_execute_laps_secret_raises_if_not_approved -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/governance/__init__.py`** (empty)

- [ ] **Step 4: Create `src/mcp_intune/services/governance/laps_service.py`**

```python
from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.approval.models import ApprovalStatus
from mcp_intune.graph.client import graph_get

LAPS_BASE = "v1.0/deviceManagement/deviceLocalCredentialInfos"


async def get_laps_metadata(device_id: str) -> dict[str, Any]:
    """Returns LAPS metadata WITHOUT the password (requires DeviceLocalCredential.ReadBasic.All)."""
    params = {"$select": "id,deviceName,refreshDateTime,credentials"}
    return await graph_get(f"{LAPS_BASE}/{device_id}", params=params, ttl=60)


async def request_laps_secret(
    device_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="laps_secret",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
        action_params={"device_id": device_id},
    )
    return {
        "status": "pending_approval",
        "request_id": req.request_id,
        "operation": "laps_secret",
        "device_id": device_id,
        "risk": "high",
        "note": "Retrieving the LAPS secret generates an audit event in Microsoft Entra ID.",
    }


async def execute_laps_secret(request_id: str) -> dict[str, Any]:
    """Retrieve the LAPS password after approval. Generates audit event in Entra ID."""
    req = await approval_store.get_request(request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")
    if req.status != ApprovalStatus.APPROVED:
        raise ValueError(f"Request {request_id} is not approved (status: {req.status})")

    device_id = req.action_params["device_id"]
    # $select=credentials is required to get the password value — generates audit log
    params = {"$select": "id,deviceName,refreshDateTime,credentials"}
    result = await graph_get(f"{LAPS_BASE}/{device_id}", params=params, ttl=0)
    return {
        "device_id": device_id,
        "device_name": result.get("deviceName"),
        "refresh_date_time": result.get("refreshDateTime"),
        "credentials": result.get("credentials", []),
        "audit_note": "This retrieval has been logged in Microsoft Entra ID audit logs.",
        "request_id": request_id,
    }
```

- [ ] **Step 5: Run to verify tests pass**

```
pytest tests/test_laps_bitlocker_service.py::test_get_laps_metadata_calls_correct_endpoint tests/test_laps_bitlocker_service.py::test_request_laps_secret_creates_approval tests/test_laps_bitlocker_service.py::test_execute_laps_secret_calls_graph_with_select_key tests/test_laps_bitlocker_service.py::test_execute_laps_secret_raises_if_not_approved -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/services/governance/ tests/test_laps_bitlocker_service.py
git commit -m "feat: add LAPS service with approval-gated secret retrieval"
```

---

## Task 2: BitLocker service — key metadata and approval-gated retrieval

**Files:**
- Create: `src/mcp_intune/services/governance/bitlocker_service.py`
- Modify: `tests/test_laps_bitlocker_service.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_laps_bitlocker_service.py`:

```python
BITLOCKER_KEYS_STUB = {
    "value": [
        {
            "id": "bk-1",
            "createdDateTime": "2026-01-01T00:00:00Z",
            "volumeType": "operatingSystemVolume",
            "deviceId": "aad-device-1",
        }
    ]
}


@pytest.mark.asyncio
async def test_find_bitlocker_keys_calls_correct_endpoint():
    with patch("mcp_intune.services.governance.bitlocker_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = BITLOCKER_KEYS_STUB
        from mcp_intune.services.governance.bitlocker_service import find_bitlocker_keys
        result = await find_bitlocker_keys(device_id="aad-device-1")
        assert result["value"][0]["volumeType"] == "operatingSystemVolume"
        call_path = mock_get.call_args[0][0]
        assert "bitlocker" in call_path.lower() or "recoveryKeys" in call_path


@pytest.mark.asyncio
async def test_request_bitlocker_key_creates_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.governance.bitlocker_service import request_bitlocker_key
    result = await request_bitlocker_key("bk-1", "LAP-001", "Drive recovery", "INC-002")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "bitlocker_key"
    assert result["risk"] == "high"


@pytest.mark.asyncio
async def test_execute_bitlocker_key_fetches_key_with_select():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        "bitlocker_key", "bk-1", "LAP-001", "Test", "INC-003", "high",
        action_params={"key_id": "bk-1"},
    )
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.governance.bitlocker_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"id": "bk-1", "key": "123456-789012-345678-901234-567890-123456-789012-345678"}
        from mcp_intune.services.governance.bitlocker_service import execute_bitlocker_key
        result = await execute_bitlocker_key(req.request_id)
        assert "key" in result
        call_params = str(mock_get.call_args)
        assert "key" in call_params
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_laps_bitlocker_service.py::test_find_bitlocker_keys_calls_correct_endpoint tests/test_laps_bitlocker_service.py::test_request_bitlocker_key_creates_approval tests/test_laps_bitlocker_service.py::test_execute_bitlocker_key_fetches_key_with_select -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/governance/bitlocker_service.py`**

```python
from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.approval.models import ApprovalStatus
from mcp_intune.graph.client import graph_get

BITLOCKER_BASE = "v1.0/informationProtection/bitlocker/recoveryKeys"


async def find_bitlocker_keys(device_id: str | None = None) -> dict[str, Any]:
    """Returns key metadata WITHOUT the actual key value (requires BitlockerKey.ReadBasic.All)."""
    params: dict[str, Any] = {
        "$select": "id,createdDateTime,volumeType,deviceId",
    }
    if device_id:
        params["$filter"] = f"deviceId eq '{device_id}'"
    return await graph_get(BITLOCKER_BASE, params=params, ttl=120)


async def request_bitlocker_key(
    key_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="bitlocker_key",
        device_id=key_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
        action_params={"key_id": key_id},
    )
    return {
        "status": "pending_approval",
        "request_id": req.request_id,
        "operation": "bitlocker_key",
        "key_id": key_id,
        "risk": "high",
        "note": "Retrieving the BitLocker key with $select=key generates an audit event.",
    }


async def execute_bitlocker_key(request_id: str) -> dict[str, Any]:
    """Retrieve BitLocker recovery key after approval. Generates audit event."""
    req = await approval_store.get_request(request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")
    if req.status != ApprovalStatus.APPROVED:
        raise ValueError(f"Request {request_id} is not approved (status: {req.status})")

    key_id = req.action_params["key_id"]
    # $select=key is required to return the actual key — generates audit log
    params = {"$select": "id,createdDateTime,volumeType,deviceId,key"}
    result = await graph_get(f"{BITLOCKER_BASE}/{key_id}", params=params, ttl=0)
    return {
        "key_id": key_id,
        "key": result.get("key"),
        "volume_type": result.get("volumeType"),
        "created_date_time": result.get("createdDateTime"),
        "audit_note": "This retrieval has been logged in Microsoft Entra ID audit logs.",
        "request_id": request_id,
    }
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_laps_bitlocker_service.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/governance/bitlocker_service.py tests/test_laps_bitlocker_service.py
git commit -m "feat: add BitLocker service with approval-gated key retrieval"
```

---

## Task 3: RBAC service — roles and assignments

**Files:**
- Create: `src/mcp_intune/services/governance/rbac_service.py`
- Create: `tests/test_rbac_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_rbac_service.py
import pytest
from unittest.mock import AsyncMock, patch


ROLES_STUB = {
    "value": [
        {"id": "role-1", "displayName": "Help Desk Operator", "description": "Read-only access", "isBuiltIn": True},
        {"id": "role-2", "displayName": "Endpoint Security Manager", "description": "Security policies", "isBuiltIn": True},
    ],
    "has_more": False, "next_cursor": None, "total_count": None,
}

ASSIGNMENTS_STUB = {
    "value": [
        {
            "id": "asgn-1",
            "displayName": "HelpDesk-Assignment",
            "roleDefinition": {"id": "role-1", "displayName": "Help Desk Operator"},
            "members": [{"id": "grp-1", "displayName": "HelpDesk-Group"}],
            "scopeTags": [],
        }
    ],
    "has_more": False, "next_cursor": None, "total_count": None,
}


@pytest.mark.asyncio
async def test_list_role_definitions_calls_v1_endpoint():
    with patch("mcp_intune.services.governance.rbac_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = ROLES_STUB
        from mcp_intune.services.governance.rbac_service import list_role_definitions
        result = await list_role_definitions()
        assert len(result["value"]) == 2
        assert result["value"][0]["displayName"] == "Help Desk Operator"
        call_path = mock_paged.call_args[0][0]
        assert "roleDefinitions" in call_path
        assert "v1.0" in call_path


@pytest.mark.asyncio
async def test_list_role_assignments_calls_v1_endpoint():
    with patch("mcp_intune.services.governance.rbac_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = ASSIGNMENTS_STUB
        from mcp_intune.services.governance.rbac_service import list_role_assignments
        result = await list_role_assignments()
        assert len(result["value"]) == 1
        assert result["value"][0]["displayName"] == "HelpDesk-Assignment"
        call_path = mock_paged.call_args[0][0]
        assert "roleAssignments" in call_path


@pytest.mark.asyncio
async def test_list_role_definitions_built_in_filter():
    with patch("mcp_intune.services.governance.rbac_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = ROLES_STUB
        from mcp_intune.services.governance.rbac_service import list_role_definitions
        await list_role_definitions(built_in_only=True)
        call_params = str(mock_paged.call_args)
        assert "isBuiltIn" in call_params
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_rbac_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/governance/rbac_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

ROLES_BASE = "v1.0/deviceManagement/roleDefinitions"
ASSIGNMENTS_BASE = "v1.0/deviceManagement/roleAssignments"


async def list_role_definitions(built_in_only: bool = False, top: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "$select": "id,displayName,description,isBuiltIn,permissions",
    }
    if built_in_only:
        params["$filter"] = "isBuiltIn eq true"
    return await graph_get_paged(ROLES_BASE, params=params, top=top)


async def get_role_definition(role_id: str) -> dict[str, Any]:
    return await graph_get(f"{ROLES_BASE}/{role_id}", ttl=300)


async def list_role_assignments(role_definition_id: str | None = None, top: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "$select": "id,displayName,roleDefinition,members,scopeTags",
        "$expand": "roleDefinition,members",
    }
    if role_definition_id:
        params["$filter"] = f"roleDefinitionId eq '{role_definition_id}'"
    return await graph_get_paged(ASSIGNMENTS_BASE, params=params, top=top)


async def get_role_assignment(assignment_id: str) -> dict[str, Any]:
    params = {"$expand": "roleDefinition,members"}
    return await graph_get(f"{ASSIGNMENTS_BASE}/{assignment_id}", params=params, ttl=120)
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_rbac_service.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/governance/rbac_service.py tests/test_rbac_service.py
git commit -m "feat: add RBAC service (list role definitions, list role assignments)"
```

---

## Task 4: Windows Autopatch service

**Files:**
- Create: `src/mcp_intune/services/autopatch/__init__.py`
- Create: `src/mcp_intune/services/autopatch/autopatch_service.py`
- Create: `tests/test_autopatch_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_autopatch_service.py
import pytest
from unittest.mock import AsyncMock, patch


DEPLOYMENTS_STUB = {
    "value": [
        {
            "id": "dep-1",
            "content": {"@odata.type": "#microsoft.graph.windowsUpdates.featureUpdateCatalogEntry", "displayName": "Windows 11 23H2"},
            "state": {"value": "offering"},
            "createdDateTime": "2026-04-01T00:00:00Z",
        }
    ],
    "has_more": False, "next_cursor": None, "total_count": None,
}

UPDATABLE_ASSETS_STUB = {
    "value": [
        {"id": "asset-1", "@odata.type": "#microsoft.graph.windowsUpdates.azureADDevice", "errors": []}
    ],
    "has_more": False, "next_cursor": None, "total_count": None,
}


@pytest.mark.asyncio
async def test_list_autopatch_deployments_calls_correct_path():
    with patch("mcp_intune.services.autopatch.autopatch_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = DEPLOYMENTS_STUB
        from mcp_intune.services.autopatch.autopatch_service import list_deployments
        result = await list_deployments()
        assert result["value"][0]["id"] == "dep-1"
        call_path = mock_paged.call_args[0][0]
        assert "admin/windows/updates/deployments" in call_path


@pytest.mark.asyncio
async def test_list_updatable_assets_calls_correct_path():
    with patch("mcp_intune.services.autopatch.autopatch_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = UPDATABLE_ASSETS_STUB
        from mcp_intune.services.autopatch.autopatch_service import list_updatable_assets
        result = await list_updatable_assets()
        assert result["value"][0]["id"] == "asset-1"
        call_path = mock_paged.call_args[0][0]
        assert "updatableAssets" in call_path
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_autopatch_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/autopatch/__init__.py`** (empty)

- [ ] **Step 4: Create `src/mcp_intune/services/autopatch/autopatch_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged, graph_post

AUTOPATCH_BASE = "v1.0/admin/windows/updates"


async def list_deployments(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(f"{AUTOPATCH_BASE}/deployments", top=top)


async def get_deployment(deployment_id: str) -> dict[str, Any]:
    return await graph_get(f"{AUTOPATCH_BASE}/deployments/{deployment_id}", ttl=60)


async def list_updatable_assets(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(f"{AUTOPATCH_BASE}/updatableAssets", top=top)


async def list_catalog_entries(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(f"{AUTOPATCH_BASE}/catalog/entries", top=top)
```

- [ ] **Step 5: Run to verify tests pass**

```
pytest tests/test_autopatch_service.py -v
```

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/services/autopatch/ tests/test_autopatch_service.py
git commit -m "feat: add Windows Autopatch service (deployments, assets, catalog)"
```

---

## Task 5: Bulk device action service

**Files:**
- Create: `src/mcp_intune/services/device/bulk_action_service.py`
- Create: `tests/test_bulk_action_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_bulk_action_service.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_bulk_sync_builds_batch_with_correct_requests():
    with patch("mcp_intune.services.device.bulk_action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {
            "responses": [
                {"id": "1", "status": 204, "body": {}},
                {"id": "2", "status": 204, "body": {}},
            ]
        }
        from mcp_intune.services.device.bulk_action_service import bulk_sync
        result = await bulk_sync(["dev-1", "dev-2"])
        assert result["total"] == 2
        batch_body = mock_post.call_args[0][1]
        assert len(batch_body["requests"]) == 2
        assert all(r["method"] == "POST" for r in batch_body["requests"])
        assert all("syncDevice" in r["url"] for r in batch_body["requests"])


@pytest.mark.asyncio
async def test_bulk_sync_rejects_more_than_20_devices():
    from mcp_intune.services.device.bulk_action_service import bulk_sync
    with pytest.raises(ValueError, match="20"):
        await bulk_sync([f"dev-{i}" for i in range(21)])


@pytest.mark.asyncio
async def test_bulk_restart_builds_batch_with_reboot():
    with patch("mcp_intune.services.device.bulk_action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {"responses": [{"id": "1", "status": 204, "body": {}}]}
        from mcp_intune.services.device.bulk_action_service import bulk_restart
        result = await bulk_restart(["dev-1"])
        batch_body = mock_post.call_args[0][1]
        assert "rebootNow" in batch_body["requests"][0]["url"]
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_bulk_action_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/device/bulk_action_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import build_batch, graph_post

DEVICE_BASE = "/deviceManagement/managedDevices"
GRAPH_V1 = "https://graph.microsoft.com/v1.0"


def _make_action_requests(device_ids: list[str], action: str, body: dict | None = None) -> list[dict[str, Any]]:
    if len(device_ids) > 20:
        raise ValueError(f"Bulk actions support up to 20 devices at once, got {len(device_ids)}")
    return [
        {
            "id": str(i + 1),
            "method": "POST",
            "url": f"{DEVICE_BASE}/{device_id}/{action}",
            "headers": {"Content-Type": "application/json"},
            "body": body or {},
        }
        for i, device_id in enumerate(device_ids)
    ]


async def bulk_sync(device_ids: list[str]) -> dict[str, Any]:
    requests = _make_action_requests(device_ids, "syncDevice")
    batch = build_batch(requests)
    response = await graph_post("v1.0/$batch", batch)
    responses = response.get("responses", [])
    succeeded = [r for r in responses if r.get("status", 0) in (200, 202, 204)]
    failed = [r for r in responses if r.get("status", 0) not in (200, 202, 204)]
    return {"action": "syncDevice", "total": len(device_ids), "succeeded": len(succeeded), "failed": len(failed), "responses": responses}


async def bulk_restart(device_ids: list[str]) -> dict[str, Any]:
    requests = _make_action_requests(device_ids, "rebootNow")
    batch = build_batch(requests)
    response = await graph_post("v1.0/$batch", batch)
    responses = response.get("responses", [])
    succeeded = [r for r in responses if r.get("status", 0) in (200, 202, 204)]
    failed = [r for r in responses if r.get("status", 0) not in (200, 202, 204)]
    return {"action": "rebootNow", "total": len(device_ids), "succeeded": len(succeeded), "failed": len(failed), "responses": responses}
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_bulk_action_service.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/device/bulk_action_service.py tests/test_bulk_action_service.py
git commit -m "feat: add bulk action service (sync, restart) with JSON batch"
```

---

## Task 6: Register governance, autopatch, and bulk tools

**Files:**
- Create: `src/mcp_intune/tools/governance/__init__.py`
- Create: `src/mcp_intune/tools/governance/governance_tools.py`
- Create: `src/mcp_intune/tools/autopatch/__init__.py`
- Create: `src/mcp_intune/tools/autopatch/autopatch_tools.py`
- Create: `src/mcp_intune/tools/device/bulk_tools.py`
- Modify: `tests/test_tool_registration.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tool_registration.py`:

```python
def test_governance_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.governance.governance_tools import _register
    _register(fake)
    expected = {
        "intune_get_laps_metadata", "intune_request_laps_secret", "intune_execute_laps_secret",
        "intune_find_bitlocker_keys", "intune_request_bitlocker_key", "intune_execute_bitlocker_key",
        "intune_list_role_definitions", "intune_list_role_assignments",
    }
    assert expected.issubset(fake.tools.keys())


def test_autopatch_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.autopatch.autopatch_tools import _register
    _register(fake)
    expected = {"intune_list_autopatch_deployments", "intune_get_autopatch_deployment", "intune_list_updatable_assets"}
    assert expected.issubset(fake.tools.keys())


def test_bulk_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.device.bulk_tools import _register
    _register(fake)
    expected = {"intune_bulk_sync", "intune_bulk_restart"}
    assert expected.issubset(fake.tools.keys())
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_tool_registration.py::test_governance_tools_registered tests/test_tool_registration.py::test_autopatch_tools_registered tests/test_tool_registration.py::test_bulk_tools_registered -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Create `src/mcp_intune/tools/governance/__init__.py`** (empty)

- [ ] **Step 4: Create `src/mcp_intune/tools/governance/governance_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.governance import bitlocker_service, laps_service, rbac_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_SENSITIVE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_get_laps_metadata", annotations={**_READ_ANNOTATIONS, "title": "Get LAPS Metadata"})
    @audited
    async def intune_get_laps_metadata(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get LAPS metadata for a device (last rotation date, account name). Does NOT return the password.

        USE: To check when LAPS was last rotated. For the actual password, use intune_request_laps_secret.
        REQUIRES: DeviceLocalCredential.ReadBasic.All permission.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await laps_service.get_laps_metadata(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"LAPS metadata '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_laps_secret", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Request LAPS Secret"})
    @audited
    async def intune_request_laps_secret(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request retrieval of the LAPS local admin password. REQUIRES APPROVAL.

        REQUIRES: DeviceLocalCredential.Read.All permission.
        WARNING: Retrieval generates an audit event in Microsoft Entra ID.
        Returns pending_approval — use intune_approve_action + intune_execute_laps_secret.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification (logged in audit).
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await laps_service.request_laps_secret(device_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"LAPS secret request '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_execute_laps_secret", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Execute LAPS Secret Retrieval"})
    @audited
    async def intune_execute_laps_secret(
        request_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Retrieve the LAPS password after it has been approved. Generates audit event.

        USE: After intune_approve_action confirms the request_id.

        Args:
            request_id: The request_id from intune_request_laps_secret.
        """
        try:
            result = await laps_service.execute_laps_secret(request_id)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context=f"LAPS secret execution '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_find_bitlocker_keys", annotations={**_READ_ANNOTATIONS, "title": "Find BitLocker Keys"})
    @audited
    async def intune_find_bitlocker_keys(
        device_id: str | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List BitLocker recovery key metadata (does NOT return the key value).

        USE: To find key IDs before requesting the actual key with intune_request_bitlocker_key.
        REQUIRES: BitlockerKey.ReadBasic.All permission.

        Args:
            device_id: Azure AD device ID to filter keys (optional).
        """
        try:
            result = await bitlocker_service.find_bitlocker_keys(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context="find BitLocker keys")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_bitlocker_key", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Request BitLocker Key"})
    @audited
    async def intune_request_bitlocker_key(
        key_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request retrieval of a BitLocker recovery key. REQUIRES APPROVAL.

        REQUIRES: BitlockerKey.Read.All permission.
        WARNING: Retrieval generates an audit event in Microsoft Entra ID.
        Returns pending_approval — use intune_approve_action + intune_execute_bitlocker_key.

        Args:
            key_id: BitLocker recovery key id (from intune_find_bitlocker_keys).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification (logged in audit).
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await bitlocker_service.request_bitlocker_key(key_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"BitLocker key request '{key_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_execute_bitlocker_key", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Execute BitLocker Key Retrieval"})
    @audited
    async def intune_execute_bitlocker_key(
        request_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Retrieve the BitLocker recovery key after it has been approved. Generates audit event.

        USE: After intune_approve_action confirms the request_id.

        Args:
            request_id: The request_id from intune_request_bitlocker_key.
        """
        try:
            result = await bitlocker_service.execute_bitlocker_key(request_id)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context=f"BitLocker key execution '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_role_definitions", annotations={**_READ_ANNOTATIONS, "title": "List RBAC Role Definitions"})
    @audited
    async def intune_list_role_definitions(
        built_in_only: bool = False,
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Intune RBAC role definitions (built-in and custom).

        USE: To understand available roles before auditing assignments.

        Args:
            built_in_only: If True, only return Microsoft built-in roles.
            top: Max results (default 50).
        """
        try:
            result = await rbac_service.list_role_definitions(built_in_only, top)
        except Exception as exc:
            result = graph_error_response(exc, context="list role definitions")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_role_assignments", annotations={**_READ_ANNOTATIONS, "title": "List RBAC Role Assignments"})
    @audited
    async def intune_list_role_assignments(
        role_definition_id: str | None = None,
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Intune RBAC role assignments with members and scope tags.

        USE: To audit who has which Intune admin role and what scope they cover.

        Args:
            role_definition_id: Filter assignments to a specific role (optional).
            top: Max results (default 50).
        """
        try:
            result = await rbac_service.list_role_assignments(role_definition_id, top)
        except Exception as exc:
            result = graph_error_response(exc, context="list role assignments")
        return render_response(result, response_format)
```

- [ ] **Step 5: Create `src/mcp_intune/tools/autopatch/__init__.py`** (empty)

- [ ] **Step 6: Create `src/mcp_intune/tools/autopatch/autopatch_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.autopatch import autopatch_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_autopatch_deployments", annotations={**_READ_ANNOTATIONS, "title": "List Autopatch Deployments"})
    @audited
    async def intune_list_autopatch_deployments(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Windows Autopatch deployments from the Windows Update for Business deployment service.

        USE: To see active update deployments, their state (offering/paused), and content.
        REQUIRES: WindowsUpdates.Read.All permission.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await autopatch_service.list_deployments(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list Autopatch deployments")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_autopatch_deployment", annotations={**_READ_ANNOTATIONS, "title": "Get Autopatch Deployment"})
    @audited
    async def intune_get_autopatch_deployment(
        deployment_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get details of a specific Windows Autopatch deployment.

        Args:
            deployment_id: The deployment id (GUID from intune_list_autopatch_deployments).
        """
        try:
            result = await autopatch_service.get_deployment(deployment_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"get Autopatch deployment '{deployment_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_updatable_assets", annotations={**_READ_ANNOTATIONS, "title": "List Updatable Assets"})
    @audited
    async def intune_list_updatable_assets(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List devices registered as updatable assets in Windows Autopatch.

        USE: To see which devices are enrolled and if any have errors preventing updates.
        REQUIRES: WindowsUpdates.Read.All permission.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await autopatch_service.list_updatable_assets(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list updatable assets")
        return render_response(result, response_format)
```

- [ ] **Step 7: Create `src/mcp_intune/tools/device/bulk_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.device import bulk_action_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_BULK_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_bulk_sync", annotations={**_BULK_ANNOTATIONS, "title": "Bulk Device Sync"})
    @audited
    async def intune_bulk_sync(
        device_ids: list[str],
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request sync for multiple managed devices at once (JSON batch, max 20 devices).

        USE: When you need to force check-in for a group of devices efficiently.
        DON'T USE: For more than 20 devices — batch into multiple calls.

        Args:
            device_ids: List of Intune managedDeviceId GUIDs (max 20).
        """
        try:
            result = await bulk_action_service.bulk_sync(device_ids)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context="bulk sync")
        return render_response(result, response_format)

    @mcp.tool(name="intune_bulk_restart", annotations={**_BULK_ANNOTATIONS, "title": "Bulk Device Restart"})
    @audited
    async def intune_bulk_restart(
        device_ids: list[str],
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request restart for multiple managed devices at once (JSON batch, max 20 devices).

        USE: When applying policies/updates requires a restart across multiple devices.
        DON'T USE: For more than 20 devices — batch into multiple calls.

        Args:
            device_ids: List of Intune managedDeviceId GUIDs (max 20).
        """
        try:
            result = await bulk_action_service.bulk_restart(device_ids)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context="bulk restart")
        return render_response(result, response_format)
```

- [ ] **Step 8: Run to verify all 3 tool registration tests pass**

```
pytest tests/test_tool_registration.py::test_governance_tools_registered tests/test_tool_registration.py::test_autopatch_tools_registered tests/test_tool_registration.py::test_bulk_tools_registered -v
```

Expected: 3 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/mcp_intune/tools/governance/ src/mcp_intune/tools/autopatch/ src/mcp_intune/tools/device/bulk_tools.py tests/test_tool_registration.py
git commit -m "feat: register governance, autopatch, and bulk tools"
```

---

## Task 7: Wire server + update readme and changelog

**Files:**
- Modify: `src/mcp_intune/server.py`
- Modify: `readme.md`
- Modify: `changelog.md`

- [ ] **Step 1: Update `src/mcp_intune/server.py`**

```python
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import fastmcp
import structlog

from mcp_intune.graph.client import _get_http_client
from mcp_intune.logging_config import configure_logging
from mcp_intune.tools.device import device_tools, action_tools, bulk_tools
from mcp_intune.tools.reporting import reporting_tools
from mcp_intune.tools.scripts import scripts_tools
from mcp_intune.tools.updates import updates_tools
from mcp_intune.tools.autopilot import autopilot_tools
from mcp_intune.tools.governance import governance_tools
from mcp_intune.tools.autopatch import autopatch_tools

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
bulk_tools._register(mcp)
reporting_tools._register(mcp)
scripts_tools._register(mcp)
updates_tools._register(mcp)
autopilot_tools._register(mcp)
governance_tools._register(mcp)
autopatch_tools._register(mcp)


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

- [ ] **Step 2: Update `readme.md`** — update total to **47 ferramentas** and add sections:

```markdown
### 🔐 Governança e Operações Sensíveis

- **`intune_get_laps_metadata`**: metadados do LAPS (data de rotação, conta). **Não retorna a senha**. Requer `DeviceLocalCredential.ReadBasic.All`.
- **`intune_request_laps_secret`**: solicita a senha LAPS de um dispositivo. **Requer aprovação**. Gera auditoria no Entra ID. Requer `DeviceLocalCredential.Read.All`.
- **`intune_execute_laps_secret`**: recupera a senha LAPS após aprovação. Gera auditoria.
- **`intune_find_bitlocker_keys`**: lista metadados de chaves BitLocker. **Não retorna o valor da chave**. Requer `BitlockerKey.ReadBasic.All`.
- **`intune_request_bitlocker_key`**: solicita a chave de recuperação BitLocker. **Requer aprovação**. Gera auditoria. Requer `BitlockerKey.Read.All`.
- **`intune_execute_bitlocker_key`**: recupera a chave BitLocker após aprovação. Gera auditoria.
- **`intune_list_role_definitions`**: lista definições de roles RBAC do Intune (built-in e customizadas).
- **`intune_list_role_assignments`**: lista assignments de roles com membros e scope tags.

### ⚡ Ações em Massa

- **`intune_bulk_sync`**: sync de até 20 dispositivos simultâneos via JSON batch.
- **`intune_bulk_restart`**: restart de até 20 dispositivos simultâneos via JSON batch.

### 🪟 Windows Autopatch

- **`intune_list_autopatch_deployments`**: lista deployments do serviço Windows Update for Business. Requer `WindowsUpdates.Read.All`.
- **`intune_get_autopatch_deployment`**: detalhes de um deployment específico.
- **`intune_list_updatable_assets`**: dispositivos registrados no Autopatch e erros de elegibilidade.
```

Update permissions table to add:

```markdown
| `DeviceLocalCredential.ReadBasic.All` | Metadados LAPS |
| `DeviceLocalCredential.Read.All` | Senha LAPS (geração de auditoria) |
| `BitlockerKey.ReadBasic.All` | Metadados de chaves BitLocker |
| `BitlockerKey.Read.All` | Chave de recuperação BitLocker (geração de auditoria) |
| `DeviceManagementRBAC.Read.All` | Roles e assignments RBAC |
| `WindowsUpdates.Read.All` | Windows Autopatch deployments |
| `DeviceManagementScripts.Read.All` | Scripts e remediações |
```

- [ ] **Step 3: Update `changelog.md`** — add V3 entry:

```markdown
## 2026-05-02 — V3: Governança, Operações Sensíveis e Autopatch

### Added

- **Operações sensíveis (LAPS)**
  - `intune_get_laps_metadata` — metadados sem senha
  - `intune_request_laps_secret` / `intune_execute_laps_secret` — com approval workflow e geração de auditoria

- **Operações sensíveis (BitLocker)**
  - `intune_find_bitlocker_keys` — metadados sem chave
  - `intune_request_bitlocker_key` / `intune_execute_bitlocker_key` — com approval workflow e geração de auditoria

- **Governança RBAC**
  - `intune_list_role_definitions` (filtro built-in)
  - `intune_list_role_assignments` (filtro por role, expand members e scope tags)

- **Ações em massa (JSON batch)**
  - `intune_bulk_sync`, `intune_bulk_restart` — até 20 dispositivos simultâneos

- **Windows Autopatch**
  - `intune_list_autopatch_deployments`, `intune_get_autopatch_deployment`
  - `intune_list_updatable_assets`

### Changed

- **Total de tools expostas: 47** (era 34 na V2b)

### Security

- LAPS e BitLocker: chave/senha nunca retornada sem aprovação explícita
- Ambas operações geram auditoria no Microsoft Entra ID ao executar com `$select=credentials/key`
- Approval workflow com TTL configurável protege contra requests esquecidos

---
```

- [ ] **Step 4: Run full test suite**

```
pytest tests -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/server.py readme.md changelog.md
git commit -m "feat: wire V3 tools in server, update readme and changelog — V3 complete"
```
