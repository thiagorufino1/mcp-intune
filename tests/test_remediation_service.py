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
    ],
    "has_more": False, "next_cursor": None, "total_count": None,
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
        mock_paged.return_value = REMEDIATIONS_STUB
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
