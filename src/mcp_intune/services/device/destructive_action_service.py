from typing import Any

from mcp_intune.approval import store as approval_store
from mcp_intune.approval.models import ApprovalStatus
from mcp_intune.graph.client import graph_delete, graph_post

DEVICE_BASE = "v1.0/deviceManagement/managedDevices"


async def request_retire(device_id: str, device_name: str, reason: str, ticket_id: str) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="retire",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="medium",
    )
    return {"status": "pending_approval", "request_id": req.request_id, "operation": "retire", "device_id": device_id}


async def request_wipe(
    device_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
    keep_enrollment_data: bool = False,
) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="wipe",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
        action_params={"keepEnrollmentData": keep_enrollment_data, "keepUserData": False},
    )
    return {"status": "pending_approval", "request_id": req.request_id, "operation": "wipe", "device_id": device_id}


async def request_delete(device_id: str, device_name: str, reason: str, ticket_id: str) -> dict[str, Any]:
    req = await approval_store.create_request(
        operation="delete",
        device_id=device_id,
        device_name=device_name,
        reason=reason,
        ticket_id=ticket_id,
        risk="high",
    )
    return {"status": "pending_approval", "request_id": req.request_id, "operation": "delete", "device_id": device_id}


async def execute_approved_action(request_id: str) -> dict[str, Any]:
    req = await approval_store.get_request(request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")
    if req.status != ApprovalStatus.APPROVED:
        raise ValueError(f"Request {request_id} is not approved (status: {req.status})")

    op = req.operation
    device_id = req.device_id

    if op == "retire":
        await graph_post(f"{DEVICE_BASE}/{device_id}/retire", {})
    elif op == "wipe":
        await graph_post(f"{DEVICE_BASE}/{device_id}/wipe", req.action_params)
    elif op == "delete":
        await graph_delete(f"{DEVICE_BASE}/{device_id}")
    else:
        raise ValueError(f"Unknown operation: {op}")

    return {"executed": op, "device_id": device_id, "request_id": request_id, "status": "executed"}
