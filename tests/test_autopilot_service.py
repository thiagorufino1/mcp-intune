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
    "has_more": False, "next_cursor": None, "total_count": None,
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
