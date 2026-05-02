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
    "has_more": False, "next_cursor": None, "total_count": None,
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
        assert "windowsUpdateForBusinessConfiguration" in call_path or "deviceConfigurations" in call_path


@pytest.mark.asyncio
async def test_get_update_ring_returns_ring_with_assignments():
    with patch("mcp_intune.services.updates.update_ring_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [UPDATE_RINGS_STUB["value"][0], RING_ASSIGNMENTS_STUB]
        from mcp_intune.services.updates.update_ring_service import get_update_ring
        result = await get_update_ring("ring-1")
        assert result["ring"]["displayName"] == "Ring-Pilot"
        assert len(result["assignments"]) == 1


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
