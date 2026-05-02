from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.approval.models import ApprovalStatus
from mcp_intune.graph.client import graph_get

LAPS_BASE = "v1.0/deviceManagement/deviceLocalCredentialInfos"


async def get_laps_metadata(device_id: str) -> dict[str, Any]:
    """Returns LAPS metadata WITHOUT the password (requires DeviceLocalCredential.ReadBasic.All)."""
    params = {"$select": "id,deviceName,refreshDateTime,credentials"}
    return await graph_get(f"{LAPS_BASE}/{device_id}", params=params, ttl=60)


async def request_laps_secret(
    device_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="laps_secret",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
        action_params={"device_id": device_id},
    )
    return {
        "status": "pending_approval",
        "request_id": req.request_id,
        "operation": "laps_secret",
        "device_id": device_id,
        "risk": "high",
        "note": "Retrieving the LAPS secret generates an audit event in Microsoft Entra ID.",
    }


async def execute_laps_secret(request_id: str) -> dict[str, Any]:
    """Retrieve the LAPS password after approval. Generates audit event in Entra ID."""
    req = await approval_store.get_request(request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")
    if req.status != ApprovalStatus.APPROVED:
        raise ValueError(f"Request {request_id} is not approved (status: {req.status})")

    device_id = req.action_params["device_id"]
    params = {"$select": "id,deviceName,refreshDateTime,credentials"}
    result = await graph_get(f"{LAPS_BASE}/{device_id}", params=params, ttl=0)
    return {
        "device_id": device_id,
        "device_name": result.get("deviceName"),
        "refresh_date_time": result.get("refreshDateTime"),
        "credentials": result.get("credentials", []),
        "audit_note": "This retrieval has been logged in Microsoft Entra ID audit logs.",
        "request_id": request_id,
    }
