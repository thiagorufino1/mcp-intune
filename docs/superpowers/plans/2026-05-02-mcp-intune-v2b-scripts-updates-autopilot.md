# MCP Intune V2b — Scripts/Remediations, Update Rings, Autopilot

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tools for proactive remediations (beta), update ring management, feature/quality/driver update profiles (beta), and Autopilot device management.

**Architecture:** Beta endpoints are wrapped with `_assert_beta_allowed(path)` in the graph client — they will raise `BetaApiNotAllowedError` unless `ALLOW_BETA_APIS=true`. Each domain gets its own service + tool module following the existing `services/<domain>/` + `tools/<domain>/` pattern. `run_remediation` (on-demand execution) is a privileged action requiring approval — reuses the existing approval store from V2.

**Tech Stack:** Python 3.12, FastMCP, httpx, pytest, pytest-asyncio, unittest.mock

---

## Codebase context

Project root: `C:\Users\thiag\OneDrive\Thiago\github\mcp-intune`

**Prerequisites:** V2 plan must be fully implemented (approval store, action_tools, reporting_tools registered in server.py).

Existing patterns:
- Service modules in `src/mcp_intune/services/<domain>/`
- Tool modules in `src/mcp_intune/tools/<domain>/` with `_register(mcp)` function
- `graph_get(path, params, ttl)`, `graph_post(path, body)`, `graph_get_all_pages(path)` from `src/mcp_intune/graph/client.py`
- `@audited` decorator, `render_response`, `graph_error_response` from utils
- Beta paths: use `"beta/deviceManagement/..."` — blocked unless `ALLOW_BETA_APIS=true`
- Approval store: `from mcp_intune.approval import store as approval_store`
- Tests: `unittest.mock.AsyncMock` + `patch("mcp_intune.services.X.Y.graph_get", ...)`
- Run tests: `pytest tests -v`

---

## File structure

```
src/mcp_intune/
  services/
    scripts/
      __init__.py          NEW (empty)
      remediation_service.py  NEW: list_remediations, get_remediation_run_state, request_remediation_run
    updates/
      __init__.py          NEW (empty)
      update_ring_service.py  NEW: list_update_rings, get_update_ring
      update_profile_service.py  NEW: list_feature/quality/driver update profiles (beta)
    autopilot/
      __init__.py          NEW (empty)
      autopilot_service.py  NEW: get_autopilot_device, list_autopilot_devices, import_autopilot_device
  tools/
    scripts/
      __init__.py          NEW (empty)
      scripts_tools.py     NEW: registers 3 remediation tools
    updates/
      __init__.py          NEW (empty)
      updates_tools.py     NEW: registers 5 update tools
    autopilot/
      __init__.py          NEW (empty)
      autopilot_tools.py   NEW: registers 3 autopilot tools
  server.py                MODIFY: register scripts, updates, autopilot tools

tests/
  test_remediation_service.py  NEW
  test_update_service.py       NEW
  test_autopilot_service.py    NEW
```

---

## Task 1: Remediation service (beta)

**Files:**
- Create: `src/mcp_intune/services/scripts/__init__.py`
- Create: `src/mcp_intune/services/scripts/remediation_service.py`
- Create: `tests/test_remediation_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_remediation_service.py
import pytest
from unittest.mock import AsyncMock, patch


REMEDIATIONS_STUB = {
    "value": [
        {
            "id": "rem-1",
            "displayName": "Fix Registry Key",
            "description": "Fixes missing registry entry",
            "publisher": "IT-Ops",
            "version": "1.0",
            "isGlobalScript": False,
        }
    ]
}

RUN_STATE_STUB = {
    "value": [
        {
            "id": "run-1",
            "managedDeviceId": "dev-abc",
            "detectionState": "success",
            "remediationState": "success",
            "lastStateUpdateDateTime": "2026-05-01T10:00:00Z",
            "preRemediationDetectionScriptOutput": "Found issue",
            "postRemediationDetectionScriptOutput": "Issue fixed",
        }
    ]
}


@pytest.mark.asyncio
async def test_list_remediations_calls_beta_endpoint():
    with patch("mcp_intune.services.scripts.remediation_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = {"value": REMEDIATIONS_STUB["value"], "has_more": False, "next_cursor": None, "total_count": None}
        from mcp_intune.services.scripts.remediation_service import list_remediations
        result = await list_remediations()
        assert len(result["value"]) == 1
        assert result["value"][0]["displayName"] == "Fix Registry Key"
        call_path = mock_paged.call_args[0][0]
        assert "beta" in call_path
        assert "deviceHealthScripts" in call_path


@pytest.mark.asyncio
async def test_get_remediation_run_state_calls_device_run_summaries():
    with patch("mcp_intune.services.scripts.remediation_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = RUN_STATE_STUB
        from mcp_intune.services.scripts.remediation_service import get_remediation_run_state
        result = await get_remediation_run_state("rem-1", device_id="dev-abc")
        assert result["value"][0]["detectionState"] == "success"
        call_path = mock_get.call_args[0][0]
        assert "rem-1" in call_path
        assert "deviceRunStates" in call_path


@pytest.mark.asyncio
async def test_request_remediation_run_creates_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.scripts.remediation_service import request_remediation_run
    result = await request_remediation_run("rem-1", "dev-abc", "Fix issue", "INC-001")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "run_remediation"
    assert "rem-1" in str(result)
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_remediation_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/scripts/__init__.py`**

Empty file.

- [ ] **Step 4: Create `src/mcp_intune/services/scripts/remediation_service.py`**

```python
from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.graph.client import graph_get, graph_get_paged, graph_post

SCRIPTS_BASE = "beta/deviceManagement/deviceHealthScripts"


async def list_remediations(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(SCRIPTS_BASE, top=top)


async def get_remediation(script_id: str) -> dict[str, Any]:
    return await graph_get(f"{SCRIPTS_BASE}/{script_id}", ttl=120)


async def get_remediation_run_state(script_id: str, device_id: str | None = None) -> dict[str, Any]:
    path = f"{SCRIPTS_BASE}/{script_id}/deviceRunStates"
    params: dict[str, Any] = {"$select": "id,managedDeviceId,detectionState,remediationState,lastStateUpdateDateTime,preRemediationDetectionScriptOutput,postRemediationDetectionScriptOutput"}
    if device_id:
        params["$filter"] = f"managedDeviceId eq '{device_id}'"
    return await graph_get(path, params=params, ttl=60)


async def request_remediation_run(
    script_id: str,
    device_id: str,
    reason: str,
    ticket_id: str,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="run_remediation",
        device_id=device_id,
        device_name=device_id,
        reason=reason,
        ticket_id=ticket_id,
        risk="medium",
        action_params={"scriptId": script_id},
    )
    return {
        "status": "pending_approval",
        "request_id": req.request_id,
        "operation": "run_remediation",
        "script_id": script_id,
        "device_id": device_id,
    }


async def execute_remediation_run(script_id: str, device_id: str) -> dict[str, Any]:
    """Execute on-demand remediation. Called only after approval."""
    body = {"scriptPolicyId": script_id, "managedDeviceId": device_id}
    await graph_post(
        f"beta/deviceManagement/managedDevices/{device_id}/initiateOnDemandProactiveRemediation",
        body,
    )
    return {"action": "initiateOnDemandProactiveRemediation", "script_id": script_id, "device_id": device_id, "status": "initiated"}
```

- [ ] **Step 5: Run to verify tests pass**

```
pytest tests/test_remediation_service.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/services/scripts/ tests/test_remediation_service.py
git commit -m "feat: add remediation service (list, run state, approval-gated execution)"
```

---

## Task 2: Update ring service (v1.0)

**Files:**
- Create: `src/mcp_intune/services/updates/__init__.py`
- Create: `src/mcp_intune/services/updates/update_ring_service.py`
- Create: `tests/test_update_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_update_service.py
import pytest
from unittest.mock import AsyncMock, patch


UPDATE_RINGS_STUB = {
    "value": [
        {
            "id": "ring-1",
            "displayName": "Ring-Pilot",
            "description": "Pilot ring",
            "qualityUpdatesDeferralPeriodInDays": 0,
            "featureUpdatesDeferralPeriodInDays": 0,
            "qualityUpdatesPaused": False,
            "featureUpdatesPaused": False,
        }
    ],
    "has_more": False,
    "next_cursor": None,
    "total_count": None,
}

RING_ASSIGNMENTS_STUB = {
    "value": [
        {"id": "asgn-1", "target": {"@odata.type": "#microsoft.graph.groupAssignmentTarget", "groupId": "grp-1"}}
    ]
}


@pytest.mark.asyncio
async def test_list_update_rings_calls_v1_endpoint():
    with patch("mcp_intune.services.updates.update_ring_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = UPDATE_RINGS_STUB
        from mcp_intune.services.updates.update_ring_service import list_update_rings
        result = await list_update_rings()
        assert len(result["value"]) == 1
        assert result["value"][0]["displayName"] == "Ring-Pilot"
        call_path = mock_paged.call_args[0][0]
        assert "v1.0" in call_path
        assert "windowsUpdateForBusinessConfiguration" in call_path


@pytest.mark.asyncio
async def test_get_update_ring_returns_ring_with_assignments():
    with patch("mcp_intune.services.updates.update_ring_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [UPDATE_RINGS_STUB["value"][0], RING_ASSIGNMENTS_STUB]
        from mcp_intune.services.updates.update_ring_service import get_update_ring
        result = await get_update_ring("ring-1")
        assert result["ring"]["displayName"] == "Ring-Pilot"
        assert len(result["assignments"]) == 1
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_update_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/updates/__init__.py`**

Empty file.

- [ ] **Step 4: Create `src/mcp_intune/services/updates/update_ring_service.py`**

```python
import asyncio
from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

UPDATE_RINGS_BASE = "v1.0/deviceManagement/deviceConfigurations"
WUB_FILTER = "isof('microsoft.graph.windowsUpdateForBusinessConfiguration')"


async def list_update_rings(top: int | None = None) -> dict[str, Any]:
    params = {
        "$filter": WUB_FILTER,
        "$select": "id,displayName,description,qualityUpdatesDeferralPeriodInDays,featureUpdatesDeferralPeriodInDays,qualityUpdatesPaused,featureUpdatesPaused,businessReadyUpdatesOnly",
    }
    return await graph_get_paged(UPDATE_RINGS_BASE, params=params, top=top)


async def get_update_ring(ring_id: str) -> dict[str, Any]:
    ring, assignments = await asyncio.gather(
        graph_get(f"{UPDATE_RINGS_BASE}/{ring_id}", ttl=120),
        graph_get(f"{UPDATE_RINGS_BASE}/{ring_id}/assignments", ttl=120),
    )
    return {
        "ring": ring,
        "assignments": assignments.get("value", []),
    }
```

- [ ] **Step 5: Run to verify tests pass**

```
pytest tests/test_update_service.py -v
```

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/services/updates/ tests/test_update_service.py
git commit -m "feat: add update ring service (list, get with assignments)"
```

---

## Task 3: Update profile service — feature, quality, driver (beta)

**Files:**
- Create: `src/mcp_intune/services/updates/update_profile_service.py`
- Modify: `tests/test_update_service.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_update_service.py`:

```python
FEATURE_PROFILES_STUB = {
    "value": [{"id": "fp-1", "displayName": "Feature 23H2", "featureUpdateVersion": "Windows 10, version 23H2"}],
    "has_more": False, "next_cursor": None, "total_count": None,
}

QUALITY_PROFILES_STUB = {
    "value": [{"id": "qp-1", "displayName": "Quality Monthly"}],
    "has_more": False, "next_cursor": None, "total_count": None,
}

DRIVER_PROFILES_STUB = {
    "value": [{"id": "dp-1", "displayName": "Drivers Auto"}],
    "has_more": False, "next_cursor": None, "total_count": None,
}


@pytest.mark.asyncio
async def test_list_feature_update_profiles_uses_beta():
    with patch("mcp_intune.services.updates.update_profile_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = FEATURE_PROFILES_STUB
        from mcp_intune.services.updates.update_profile_service import list_feature_update_profiles
        result = await list_feature_update_profiles()
        assert result["value"][0]["displayName"] == "Feature 23H2"
        call_path = mock_paged.call_args[0][0]
        assert "beta" in call_path
        assert "windowsFeatureUpdateProfiles" in call_path


@pytest.mark.asyncio
async def test_list_quality_update_profiles_uses_beta():
    with patch("mcp_intune.services.updates.update_profile_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = QUALITY_PROFILES_STUB
        from mcp_intune.services.updates.update_profile_service import list_quality_update_profiles
        result = await list_quality_update_profiles()
        call_path = mock_paged.call_args[0][0]
        assert "windowsQualityUpdateProfiles" in call_path


@pytest.mark.asyncio
async def test_list_driver_update_profiles_uses_beta():
    with patch("mcp_intune.services.updates.update_profile_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = DRIVER_PROFILES_STUB
        from mcp_intune.services.updates.update_profile_service import list_driver_update_profiles
        result = await list_driver_update_profiles()
        call_path = mock_paged.call_args[0][0]
        assert "windowsDriverUpdateProfiles" in call_path
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_update_service.py::test_list_feature_update_profiles_uses_beta tests/test_update_service.py::test_list_quality_update_profiles_uses_beta tests/test_update_service.py::test_list_driver_update_profiles_uses_beta -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/updates/update_profile_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

FEATURE_BASE = "beta/deviceManagement/windowsFeatureUpdateProfiles"
QUALITY_BASE = "beta/deviceManagement/windowsQualityUpdateProfiles"
DRIVER_BASE = "beta/deviceManagement/windowsDriverUpdateProfiles"


async def list_feature_update_profiles(top: int | None = None) -> dict[str, Any]:
    params = {"$select": "id,displayName,description,featureUpdateVersion,deployableContentDisplayName,endOfSupportDate"}
    return await graph_get_paged(FEATURE_BASE, params=params, top=top)


async def get_feature_update_profile(profile_id: str) -> dict[str, Any]:
    return await graph_get(f"{FEATURE_BASE}/{profile_id}", ttl=120)


async def list_quality_update_profiles(top: int | None = None) -> dict[str, Any]:
    params = {"$select": "id,displayName,description,releaseDateDisplayName"}
    return await graph_get_paged(QUALITY_BASE, params=params, top=top)


async def get_quality_update_profile(profile_id: str) -> dict[str, Any]:
    return await graph_get(f"{QUALITY_BASE}/{profile_id}", ttl=120)


async def list_driver_update_profiles(top: int | None = None) -> dict[str, Any]:
    params = {"$select": "id,displayName,description,approvalType,deploymentDeferralInDays"}
    return await graph_get_paged(DRIVER_BASE, params=params, top=top)


async def get_driver_update_profile(profile_id: str) -> dict[str, Any]:
    return await graph_get(f"{DRIVER_BASE}/{profile_id}", ttl=120)
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/test_update_service.py -v
```

Expected: all 5 update tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_intune/services/updates/update_profile_service.py tests/test_update_service.py
git commit -m "feat: add update profile service (feature, quality, driver — beta)"
```

---

## Task 4: Autopilot service

**Files:**
- Create: `src/mcp_intune/services/autopilot/__init__.py`
- Create: `src/mcp_intune/services/autopilot/autopilot_service.py`
- Create: `tests/test_autopilot_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_autopilot_service.py
import pytest
from unittest.mock import AsyncMock, patch


AUTOPILOT_DEVICE_STUB = {
    "id": "ap-1",
    "serialNumber": "SN-XYZ",
    "model": "Latitude 7440",
    "manufacturer": "Dell",
    "managedDeviceId": "dev-abc",
    "userPrincipalName": "user@empresa.com",
    "azureActiveDirectoryDeviceId": "aad-1",
    "deploymentProfileAssignmentStatus": "assigned",
}

AUTOPILOT_LIST_STUB = {
    "value": [AUTOPILOT_DEVICE_STUB],
    "has_more": False,
    "next_cursor": None,
    "total_count": None,
}


@pytest.mark.asyncio
async def test_list_autopilot_devices_calls_correct_endpoint():
    with patch("mcp_intune.services.autopilot.autopilot_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = AUTOPILOT_LIST_STUB
        from mcp_intune.services.autopilot.autopilot_service import list_autopilot_devices
        result = await list_autopilot_devices()
        assert result["value"][0]["serialNumber"] == "SN-XYZ"
        call_path = mock_paged.call_args[0][0]
        assert "windowsAutopilotDeviceIdentities" in call_path


@pytest.mark.asyncio
async def test_get_autopilot_device_by_serial():
    with patch("mcp_intune.services.autopilot.autopilot_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = AUTOPILOT_LIST_STUB
        from mcp_intune.services.autopilot.autopilot_service import get_autopilot_device_by_serial
        result = await get_autopilot_device_by_serial("SN-XYZ")
        assert result["serialNumber"] == "SN-XYZ"
        call_args = str(mock_paged.call_args)
        assert "SN-XYZ" in call_args


@pytest.mark.asyncio
async def test_get_autopilot_device_by_serial_returns_none_when_not_found():
    with patch("mcp_intune.services.autopilot.autopilot_service.graph_get_paged", new_callable=AsyncMock) as mock_paged:
        mock_paged.return_value = {"value": [], "has_more": False, "next_cursor": None, "total_count": None}
        from mcp_intune.services.autopilot.autopilot_service import get_autopilot_device_by_serial
        result = await get_autopilot_device_by_serial("SN-NOTFOUND")
        assert result is None
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_autopilot_service.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `src/mcp_intune/services/autopilot/__init__.py`**

Empty file.

- [ ] **Step 4: Create `src/mcp_intune/services/autopilot/autopilot_service.py`**

```python
from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged, graph_post

AUTOPILOT_BASE = "v1.0/deviceManagement/windowsAutopilotDeviceIdentities"
SELECT = "id,serialNumber,model,manufacturer,managedDeviceId,userPrincipalName,azureActiveDirectoryDeviceId,deploymentProfileAssignmentStatus,groupTag,purchaseOrderIdentifier"


async def list_autopilot_devices(top: int | None = None) -> dict[str, Any]:
    params = {"$select": SELECT}
    return await graph_get_paged(AUTOPILOT_BASE, params=params, top=top)


async def get_autopilot_device(device_identity_id: str) -> dict[str, Any]:
    return await graph_get(f"{AUTOPILOT_BASE}/{device_identity_id}", params={"$select": SELECT}, ttl=120)


async def get_autopilot_device_by_serial(serial_number: str) -> dict[str, Any] | None:
    safe = serial_number.replace("'", "''")
    params = {"$filter": f"serialNumber eq '{safe}'", "$select": SELECT}
    result = await graph_get_paged(AUTOPILOT_BASE, params=params)
    items = result.get("value", [])
    return items[0] if items else None


async def import_autopilot_device(
    serial_number: str,
    hardware_hash: str,
    group_tag: str | None = None,
    assigned_user_principal_name: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "serialNumber": serial_number,
        "hardwareIdentifier": hardware_hash,
    }
    if group_tag:
        body["groupTag"] = group_tag
    if assigned_user_principal_name:
        body["assignedUserPrincipalName"] = assigned_user_principal_name
    return await graph_post(AUTOPILOT_BASE, body)
```

- [ ] **Step 5: Run to verify tests pass**

```
pytest tests/test_autopilot_service.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_intune/services/autopilot/ tests/test_autopilot_service.py
git commit -m "feat: add Autopilot service (list, get by serial, import)"
```

---

## Task 5: Register scripts, updates, and autopilot tools

**Files:**
- Create: `src/mcp_intune/tools/scripts/__init__.py`
- Create: `src/mcp_intune/tools/scripts/scripts_tools.py`
- Create: `src/mcp_intune/tools/updates/__init__.py`
- Create: `src/mcp_intune/tools/updates/updates_tools.py`
- Create: `src/mcp_intune/tools/autopilot/__init__.py`
- Create: `src/mcp_intune/tools/autopilot/autopilot_tools.py`
- Modify: `tests/test_tool_registration.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tool_registration.py`:

```python
def test_scripts_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.scripts.scripts_tools import _register
    _register(fake)
    expected = {"intune_list_remediations", "intune_get_remediation_run_state", "intune_request_remediation_run"}
    assert expected.issubset(fake.tools.keys())


def test_updates_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.updates.updates_tools import _register
    _register(fake)
    expected = {
        "intune_list_update_rings", "intune_get_update_ring",
        "intune_list_feature_update_profiles", "intune_list_quality_update_profiles",
        "intune_list_driver_update_profiles",
    }
    assert expected.issubset(fake.tools.keys())


def test_autopilot_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.autopilot.autopilot_tools import _register
    _register(fake)
    expected = {"intune_list_autopilot_devices", "intune_get_autopilot_device_by_serial", "intune_import_autopilot_device"}
    assert expected.issubset(fake.tools.keys())
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_tool_registration.py::test_scripts_tools_registered tests/test_tool_registration.py::test_updates_tools_registered tests/test_tool_registration.py::test_autopilot_tools_registered -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Create `src/mcp_intune/tools/scripts/__init__.py`** (empty)

- [ ] **Step 4: Create `src/mcp_intune/tools/scripts/scripts_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.scripts import remediation_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_WRITE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_remediations", annotations={**_READ_ANNOTATIONS, "title": "List Proactive Remediations"})
    @audited
    async def intune_list_remediations(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List all proactive remediation scripts (deviceHealthScripts) in the tenant.

        REQUIRES: ALLOW_BETA_APIS=true and DeviceManagementScripts.Read.All permission.
        USE: To see available remediations before calling intune_request_remediation_run.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await remediation_service.list_remediations(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list remediations")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_remediation_run_state", annotations={**_READ_ANNOTATIONS, "title": "Get Remediation Run State"})
    @audited
    async def intune_get_remediation_run_state(
        script_id: str,
        device_id: str | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get per-device run state for a proactive remediation script.

        REQUIRES: ALLOW_BETA_APIS=true.
        USE: To diagnose why a remediation succeeded or failed on a specific device.

        Args:
            script_id: The deviceHealthScript id (GUID).
            device_id: Filter to a specific managed device id (optional).
        """
        try:
            result = await remediation_service.get_remediation_run_state(script_id, device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"remediation run state '{script_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_remediation_run", annotations={**_WRITE_ANNOTATIONS, "title": "Request On-Demand Remediation"})
    @audited
    async def intune_request_remediation_run(
        script_id: str,
        device_id: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request on-demand execution of a proactive remediation on a specific device. REQUIRES APPROVAL.

        REQUIRES: ALLOW_BETA_APIS=true and DeviceManagementManagedDevices.PrivilegedOperations.All.
        Returns pending_approval — use intune_approve_action + intune_execute_action.

        Args:
            script_id: The deviceHealthScript id (GUID).
            device_id: The managed device id (GUID).
            reason: Business justification.
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await remediation_service.request_remediation_run(script_id, device_id, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"remediation run '{script_id}'")
        return render_response(result, response_format)
```

- [ ] **Step 5: Create `src/mcp_intune/tools/updates/__init__.py`** (empty)

- [ ] **Step 6: Create `src/mcp_intune/tools/updates/updates_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.updates import update_profile_service, update_ring_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_update_rings", annotations={**_READ_ANNOTATIONS, "title": "List Windows Update Rings"})
    @audited
    async def intune_list_update_rings(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Windows Update for Business (WUfB) update rings.

        USE: To see deferral settings, pause state, and ring hierarchy for Windows updates.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_ring_service.list_update_rings(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list update rings")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_update_ring", annotations={**_READ_ANNOTATIONS, "title": "Get Update Ring Details"})
    @audited
    async def intune_get_update_ring(
        ring_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get a specific update ring with its group assignments.

        USE: When you need deferral days, pause status, and assigned groups for a ring.

        Args:
            ring_id: The update ring configuration id (GUID).
        """
        try:
            result = await update_ring_service.get_update_ring(ring_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"get update ring '{ring_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_feature_update_profiles", annotations={**_READ_ANNOTATIONS, "title": "List Feature Update Profiles"})
    @audited
    async def intune_list_feature_update_profiles(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Windows feature update profiles (target Windows version).

        REQUIRES: ALLOW_BETA_APIS=true.
        USE: To see which devices are targeted at which Windows feature version.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_profile_service.list_feature_update_profiles(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list feature update profiles")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_quality_update_profiles", annotations={**_READ_ANNOTATIONS, "title": "List Quality Update Profiles"})
    @audited
    async def intune_list_quality_update_profiles(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Windows quality (monthly patch) update profiles.

        REQUIRES: ALLOW_BETA_APIS=true.
        USE: To see targeted monthly patch cadence by group.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_profile_service.list_quality_update_profiles(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list quality update profiles")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_driver_update_profiles", annotations={**_READ_ANNOTATIONS, "title": "List Driver Update Profiles"})
    @audited
    async def intune_list_driver_update_profiles(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Windows driver update profiles (automated vs manual driver approval).

        REQUIRES: ALLOW_BETA_APIS=true.
        USE: When investigating driver update issues or approval backlog.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_profile_service.list_driver_update_profiles(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list driver update profiles")
        return render_response(result, response_format)
```

- [ ] **Step 7: Create `src/mcp_intune/tools/autopilot/__init__.py`** (empty)

- [ ] **Step 8: Create `src/mcp_intune/tools/autopilot/autopilot_tools.py`**

```python
from typing import Any

import fastmcp

from mcp_intune.services.autopilot import autopilot_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_WRITE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_autopilot_devices", annotations={**_READ_ANNOTATIONS, "title": "List Autopilot Devices"})
    @audited
    async def intune_list_autopilot_devices(
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List Windows Autopilot device identities registered in the tenant.

        USE: To see enrolled Autopilot devices, their serial numbers, and profile assignment status.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await autopilot_service.list_autopilot_devices(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list autopilot devices")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_autopilot_device_by_serial", annotations={**_READ_ANNOTATIONS, "title": "Get Autopilot Device by Serial"})
    @audited
    async def intune_get_autopilot_device_by_serial(
        serial_number: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Find a specific Autopilot device identity by serial number.

        USE: Before importing a device, to check if it's already registered.

        Args:
            serial_number: Device serial number (exact match).
        """
        try:
            device = await autopilot_service.get_autopilot_device_by_serial(serial_number)
            result = device if device is not None else {"found": False, "serial_number": serial_number}
        except Exception as exc:
            result = graph_error_response(exc, context=f"get autopilot device '{serial_number}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_import_autopilot_device", annotations={**_WRITE_ANNOTATIONS, "title": "Import Autopilot Device"})
    @audited
    async def intune_import_autopilot_device(
        serial_number: str,
        hardware_hash: str,
        group_tag: str | None = None,
        assigned_user_principal_name: str | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Import a new device into Windows Autopilot using hardware hash.

        USE: To register a new device for zero-touch provisioning.
        NOTE: Hardware hash must be obtained from the device using Get-WindowsAutoPilotInfo.

        Args:
            serial_number: Device serial number.
            hardware_hash: Base64 hardware hash from Get-WindowsAutoPilotInfo.
            group_tag: Optional Autopilot group tag for profile targeting.
            assigned_user_principal_name: Optional UPN to pre-assign the device.
        """
        try:
            result = await autopilot_service.import_autopilot_device(
                serial_number, hardware_hash, group_tag, assigned_user_principal_name
            )
        except Exception as exc:
            result = graph_error_response(exc, context=f"import autopilot device '{serial_number}'")
        return render_response(result, response_format)
```

- [ ] **Step 9: Run to verify all 3 registration tests pass**

```
pytest tests/test_tool_registration.py::test_scripts_tools_registered tests/test_tool_registration.py::test_updates_tools_registered tests/test_tool_registration.py::test_autopilot_tools_registered -v
```

Expected: 3 tests PASS

- [ ] **Step 10: Commit**

```bash
git add src/mcp_intune/tools/scripts/ src/mcp_intune/tools/updates/ src/mcp_intune/tools/autopilot/ tests/test_tool_registration.py
git commit -m "feat: register scripts, updates, and autopilot tools"
```

---

## Task 6: Wire server + update readme and changelog

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
from mcp_intune.tools.device import device_tools, action_tools
from mcp_intune.tools.reporting import reporting_tools
from mcp_intune.tools.scripts import scripts_tools
from mcp_intune.tools.updates import updates_tools
from mcp_intune.tools.autopilot import autopilot_tools

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
scripts_tools._register(mcp)
updates_tools._register(mcp)
autopilot_tools._register(mcp)


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

- [ ] **Step 2: Update `readme.md`** — update total to **34 ferramentas** and add sections:

```markdown
### 🔧 Remediações (Proativas)

- **`intune_list_remediations`**: lista todos os scripts de remediação proativa (deviceHealthScripts). Requer `ALLOW_BETA_APIS=true`.
- **`intune_get_remediation_run_state`**: estado de execução de um script por dispositivo (detection e remediation state). Requer `ALLOW_BETA_APIS=true`.
- **`intune_request_remediation_run`**: execução on-demand de remediação num dispositivo específico. **Requer aprovação** + `ALLOW_BETA_APIS=true`.

### 🔄 Atualizações Windows

- **`intune_list_update_rings`**: lista update rings WUfB com deferral e pause status (v1.0).
- **`intune_get_update_ring`**: detalhes de um ring com grupos atribuídos (v1.0).
- **`intune_list_feature_update_profiles`**: perfis de versão alvo de feature update. Requer `ALLOW_BETA_APIS=true`.
- **`intune_list_quality_update_profiles`**: perfis de patch mensal. Requer `ALLOW_BETA_APIS=true`.
- **`intune_list_driver_update_profiles`**: perfis de atualização de drivers. Requer `ALLOW_BETA_APIS=true`.

### 🚀 Autopilot

- **`intune_list_autopilot_devices`**: lista identidades Autopilot com status de atribuição de perfil.
- **`intune_get_autopilot_device_by_serial`**: encontra dispositivo Autopilot por número de série.
- **`intune_import_autopilot_device`**: importa novo dispositivo para Autopilot via hardware hash.
```

- [ ] **Step 3: Update `changelog.md`** — add entry:

```markdown
## 2026-05-02 — V2b: Scripts, Atualizações e Autopilot

### Added

- **Remediações proativas (beta)**
  - `intune_list_remediations`, `intune_get_remediation_run_state`
  - `intune_request_remediation_run` — execução on-demand com approval workflow

- **Update rings (v1.0)**
  - `intune_list_update_rings`, `intune_get_update_ring` (com assignments)

- **Update profiles (beta)**
  - `intune_list_feature_update_profiles`
  - `intune_list_quality_update_profiles`
  - `intune_list_driver_update_profiles`

- **Autopilot**
  - `intune_list_autopilot_devices`
  - `intune_get_autopilot_device_by_serial`
  - `intune_import_autopilot_device`

### Changed

- **Total de tools expostas: 34** (era 23 na V2)

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
git commit -m "feat: wire V2b tools in server, update readme and changelog"
```
