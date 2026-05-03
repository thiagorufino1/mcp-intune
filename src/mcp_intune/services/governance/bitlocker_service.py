from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.approval.models import ApprovalStatus
from mcp_intune.graph.client import graph_get

BITLOCKER_BASE = "v1.0/informationProtection/bitlocker/recoveryKeys"


async def find_bitlocker_keys(device_id: str | None = None) -> dict[str, Any]:
    """Returns key metadata WITHOUT the actual key value (requires BitlockerKey.ReadBasic.All)."""
    params: dict[str, Any] = {"$select": "id,createdDateTime,volumeType,deviceId"}
    if device_id:
        safe_device_id = device_id.replace("'", "''")
        params["$filter"] = f"deviceId eq '{safe_device_id}'"
    return await graph_get(BITLOCKER_BASE, params=params, ttl=120)


async def request_bitlocker_key(
    key_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="bitlocker_key",
        device_id=key_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
        action_params={"key_id": key_id},
    )
    return {
        "status": "pending_approval",
        "request_id": req.request_id,
        "operation": "bitlocker_key",
        "key_id": key_id,
        "risk": "high",
        "note": "Retrieving the BitLocker key with $select=key generates an audit event.",
    }


async def execute_bitlocker_key(request_id: str) -> dict[str, Any]:
    """Retrieve BitLocker recovery key after approval. Generates audit event."""
    req = await approval_store.get_request(request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")
    if req.status != ApprovalStatus.APPROVED:
        raise ValueError(f"Request {request_id} is not approved (status: {req.status})")

    key_id = req.action_params["key_id"]
    params = {"$select": "id,createdDateTime,volumeType,deviceId,key"}
    result = await graph_get(f"{BITLOCKER_BASE}/{key_id}", params=params, ttl=0)
    return {
        "key_id": key_id,
        "key": result.get("key"),
        "volume_type": result.get("volumeType"),
        "created_date_time": result.get("createdDateTime"),
        "audit_note": "This retrieval has been logged in Microsoft Entra ID audit logs.",
        "request_id": request_id,
    }
