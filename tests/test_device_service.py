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
