from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

ROLES_BASE = "v1.0/deviceManagement/roleDefinitions"
ASSIGNMENTS_BASE = "v1.0/deviceManagement/roleAssignments"


async def list_role_definitions(built_in_only: bool = False, top: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"$select": "id,displayName,description,isBuiltIn,permissions"}
    if built_in_only:
        params["$filter"] = "isBuiltIn eq true"
    return await graph_get_paged(ROLES_BASE, params=params, top=top)


# TODO: expose get_role_definition and get_role_assignment tools
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


# TODO: expose get_role_definition and get_role_assignment tools
async def get_role_assignment(assignment_id: str) -> dict[str, Any]:
    params = {"$expand": "roleDefinition,members"}
    return await graph_get(f"{ASSIGNMENTS_BASE}/{assignment_id}", params=params, ttl=120)
