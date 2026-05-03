from typing import Any

import fastmcp

from mcp_intune.services.device import action_service, destructive_action_service
from mcp_intune.approval import store as approval_store
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_SAFE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}
_DESTRUCTIVE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False}
_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_request_sync", annotations={**_SAFE_ANNOTATIONS, "title": "Request Device Sync"})
    @audited
    async def intune_request_sync(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Initiate a sync for a managed device (non-destructive, executes immediately).

        USE: When device data in Intune is stale or you want to force a policy check-in.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await action_service.request_sync(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"sync device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_restart", annotations={**_SAFE_ANNOTATIONS, "title": "Request Device Restart"})
    @audited
    async def intune_request_restart(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request a remote reboot of a managed device (non-destructive, executes immediately).

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await action_service.request_restart(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"restart device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_scan", annotations={**_SAFE_ANNOTATIONS, "title": "Request Defender Scan"})
    @audited
    async def intune_request_scan(
        device_id: str,
        quick_scan: bool = True,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Initiate a Windows Defender scan on a managed device (executes immediately).

        Args:
            device_id: Intune managedDeviceId (GUID).
            quick_scan: True for quick scan (default), False for full scan.
        """
        try:
            result = await action_service.request_scan(device_id, quick_scan)
        except Exception as exc:
            result = graph_error_response(exc, context=f"scan device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_locate", annotations={**_SAFE_ANNOTATIONS, "title": "Request Device Location"})
    @audited
    async def intune_request_locate(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request location of a managed device (device must be online).

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await action_service.request_locate(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"locate device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_retire", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Request Device Retire"})
    @audited
    async def intune_request_retire(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request retire of a managed device. REQUIRES APPROVAL before execution.

        Returns pending_approval status. Use intune_approve_action + intune_execute_action to complete.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable name (for audit trail).
            reason: Business justification.
            ticket_id: ITSM ticket reference (e.g. INC-12345).
        """
        try:
            result = await destructive_action_service.request_retire(device_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"retire device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_wipe", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Request Device Wipe"})
    @audited
    async def intune_request_wipe(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        keep_enrollment_data: bool = False,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request full wipe of a managed device. REQUIRES APPROVAL before execution.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable name (for audit trail).
            reason: Business justification.
            ticket_id: ITSM ticket reference.
            keep_enrollment_data: If True, device re-enrolls after wipe (default False).
        """
        try:
            result = await destructive_action_service.request_wipe(device_id, device_name, reason, ticket_id, keep_enrollment_data)
        except Exception as exc:
            result = graph_error_response(exc, context=f"wipe device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_delete", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Request Device Delete"})
    @audited
    async def intune_request_delete(
        device_id: str,
        device_name: str,
        reason: str,
        ticket_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Request deletion of a managed device record from Intune. REQUIRES APPROVAL.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable name (for audit trail).
            reason: Business justification.
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await destructive_action_service.request_delete(device_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"delete device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_pending_actions", annotations={**_READ_ANNOTATIONS, "title": "List Pending Approval Requests"})
    @audited
    async def intune_list_pending_actions(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List all pending device actions waiting for approval.

        USE: To see what actions are queued and need a decision.
        """
        try:
            pending = await approval_store.list_pending()
            result = {
                "pending": [
                    {
                        "request_id": r.request_id,
                        "operation": r.operation,
                        "device_id": r.device_id,
                        "device_name": r.device_name,
                        "risk": r.risk,
                        "reason": r.reason,
                        "ticket_id": r.ticket_id,
                        "requested_at": r.requested_at.isoformat(),
                        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                    }
                    for r in pending
                ],
                "count": len(pending),
            }
        except Exception as exc:
            result = graph_error_response(exc, context="list pending actions")
        return render_response(result, response_format)

    @mcp.tool(name="intune_approve_action", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Approve Pending Action"})
    @audited
    async def intune_approve_action(
        request_id: str,
        comment: str = "",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Approve a pending device action request. Does NOT execute — call intune_execute_action next.

        Args:
            request_id: The request_id from intune_request_retire/wipe/delete.
            comment: Optional approval comment for audit trail.
        """
        try:
            req = await approval_store.decide(request_id, approve=True, comment=comment)
            if req is None:
                result = {"error": f"Request {request_id} not found"}
            else:
                result = {
                    "request_id": req.request_id,
                    "status": req.status,
                    "operation": req.operation,
                    "device_id": req.device_id,
                    "next_step": "Call intune_execute_action to run the approved action",
                }
        except Exception as exc:
            result = graph_error_response(exc, context=f"approve request '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_deny_action", annotations={**_SAFE_ANNOTATIONS, "title": "Deny Pending Action"})
    @audited
    async def intune_deny_action(
        request_id: str,
        comment: str = "",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Deny a pending device action request.

        Args:
            request_id: The request_id from intune_request_retire/wipe/delete.
            comment: Reason for denial (recommended for audit trail).
        """
        try:
            req = await approval_store.decide(request_id, approve=False, comment=comment)
            if req is None:
                result = {"error": f"Request {request_id} not found"}
            else:
                result = {"request_id": req.request_id, "status": req.status, "operation": req.operation}
        except Exception as exc:
            result = graph_error_response(exc, context=f"deny request '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_execute_action", annotations={**_DESTRUCTIVE_ANNOTATIONS, "title": "Execute Approved Action"})
    @audited
    async def intune_execute_action(
        request_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Execute a previously approved device action against Microsoft Graph.

        USE: After intune_approve_action confirms the request. Will fail if not approved.

        Args:
            request_id: The request_id from the original request tool.
        """
        try:
            result = await destructive_action_service.execute_approved_action(request_id)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context=f"execute action '{request_id}'")
        return render_response(result, response_format)
