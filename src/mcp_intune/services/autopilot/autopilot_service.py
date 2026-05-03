from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged, graph_post

AUTOPILOT_BASE = "v1.0/deviceManagement/windowsAutopilotDeviceIdentities"
SELECT = "id,serialNumber,model,manufacturer,managedDeviceId,userPrincipalName,azureActiveDirectoryDeviceId,deploymentProfileAssignmentStatus,groupTag,purchaseOrderIdentifier"


async def list_autopilot_devices(top: int | None = None) -> dict[str, Any]:
    params = {"$select": SELECT}
    return await graph_get_paged(AUTOPILOT_BASE, params=params, top=top)


# TODO: expose as intune_get_autopilot_device tool
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
