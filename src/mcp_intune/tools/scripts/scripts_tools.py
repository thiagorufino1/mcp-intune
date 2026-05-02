from typing import Any
import fastmcp
from mcp_intune.services.scripts import remediation_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_WRITE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_remediations", annotations={**_READ_ANNOTATIONS, "title": "List Proactive Remediations"})
    @audited
    async def intune_list_remediations(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List all proactive remediation scripts (deviceHealthScripts) in the tenant.

        REQUIRES: ALLOW_BETA_APIS=true and DeviceManagementScripts.Read.All.
        USE: To see available remediations before calling intune_request_remediation_run.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await remediation_service.list_remediations(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list remediations")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_remediation_run_state", annotations={**_READ_ANNOTATIONS, "title": "Get Remediation Run State"})
    @audited
    async def intune_get_remediation_run_state(script_id: str, device_id: str | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Get per-device run state for a proactive remediation script.

        REQUIRES: ALLOW_BETA_APIS=true.

        Args:
            script_id: The deviceHealthScript id (GUID).
            device_id: Filter to a specific managed device id (optional).
        """
        try:
            result = await remediation_service.get_remediation_run_state(script_id, device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"remediation run state '{script_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_remediation_run", annotations={**_WRITE_ANNOTATIONS, "title": "Request On-Demand Remediation"})
    @audited
    async def intune_request_remediation_run(script_id: str, device_id: str, reason: str, ticket_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Request on-demand execution of a proactive remediation. REQUIRES APPROVAL.

        REQUIRES: ALLOW_BETA_APIS=true and DeviceManagementManagedDevices.PrivilegedOperations.All.
        Returns pending_approval — use intune_approve_action + intune_execute_action.

        Args:
            script_id: The deviceHealthScript id (GUID).
            device_id: The managed device id (GUID).
            reason: Business justification.
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await remediation_service.request_remediation_run(script_id, device_id, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"remediation run '{script_id}'")
        return render_response(result, response_format)
