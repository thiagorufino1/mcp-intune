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
