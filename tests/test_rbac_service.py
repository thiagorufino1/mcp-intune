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
