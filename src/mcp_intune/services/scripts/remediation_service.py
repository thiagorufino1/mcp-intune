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
    body = {"scriptPolicyId": script_id, "managedDeviceId": device_id}
    await graph_post(
        f"beta/deviceManagement/managedDevices/{device_id}/initiateOnDemandProactiveRemediation",
        body,
    )
    return {"action": "initiateOnDemandProactiveRemediation", "script_id": script_id, "device_id": device_id, "status": "initiated"}
