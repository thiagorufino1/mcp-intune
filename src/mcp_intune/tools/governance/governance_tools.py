from typing import Any

import fastmcp

from mcp_intune.services.governance import bitlocker_service, laps_service, rbac_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_SENSITIVE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_get_laps_metadata", annotations={**_READ_ANNOTATIONS, "title": "Get LAPS Metadata"})
    @audited
    async def intune_get_laps_metadata(device_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Get LAPS metadata for a device (last rotation date, account name). Does NOT return the password.

        USE: To check when LAPS was last rotated. For the password, use intune_request_laps_secret.
        REQUIRES: DeviceLocalCredential.ReadBasic.All permission.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await laps_service.get_laps_metadata(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"LAPS metadata '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_laps_secret", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Request LAPS Secret"})
    @audited
    async def intune_request_laps_secret(device_id: str, device_name: str, reason: str, ticket_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Request retrieval of the LAPS local admin password. REQUIRES APPROVAL.

        REQUIRES: DeviceLocalCredential.Read.All permission.
        WARNING: Retrieval generates an audit event in Microsoft Entra ID.
        Returns pending_approval — use intune_approve_action + intune_execute_laps_secret.

        Args:
            device_id: Intune managedDeviceId (GUID).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification (logged in audit).
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await laps_service.request_laps_secret(device_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"LAPS secret request '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_execute_laps_secret", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Execute LAPS Secret Retrieval"})
    @audited
    async def intune_execute_laps_secret(request_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Retrieve the LAPS password after it has been approved. Generates audit event.

        USE: After intune_approve_action confirms the request_id.

        Args:
            request_id: The request_id from intune_request_laps_secret.
        """
        try:
            result = await laps_service.execute_laps_secret(request_id)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context=f"LAPS secret execution '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_find_bitlocker_keys", annotations={**_READ_ANNOTATIONS, "title": "Find BitLocker Keys"})
    @audited
    async def intune_find_bitlocker_keys(device_id: str | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List BitLocker recovery key metadata (does NOT return the key value).

        USE: To find key IDs before requesting the actual key with intune_request_bitlocker_key.
        REQUIRES: BitlockerKey.ReadBasic.All permission.

        Args:
            device_id: Azure AD device ID to filter keys (optional).
        """
        try:
            result = await bitlocker_service.find_bitlocker_keys(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context="find BitLocker keys")
        return render_response(result, response_format)

    @mcp.tool(name="intune_request_bitlocker_key", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Request BitLocker Key"})
    @audited
    async def intune_request_bitlocker_key(key_id: str, device_name: str, reason: str, ticket_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Request retrieval of a BitLocker recovery key. REQUIRES APPROVAL.

        REQUIRES: BitlockerKey.Read.All permission.
        WARNING: Retrieval generates an audit event in Microsoft Entra ID.
        Returns pending_approval — use intune_approve_action + intune_execute_bitlocker_key.

        Args:
            key_id: BitLocker recovery key id (from intune_find_bitlocker_keys).
            device_name: Human-readable device name (for audit trail).
            reason: Business justification (logged in audit).
            ticket_id: ITSM ticket reference.
        """
        try:
            result = await bitlocker_service.request_bitlocker_key(key_id, device_name, reason, ticket_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"BitLocker key request '{key_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_execute_bitlocker_key", annotations={**_SENSITIVE_ANNOTATIONS, "title": "Execute BitLocker Key Retrieval"})
    @audited
    async def intune_execute_bitlocker_key(request_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Retrieve the BitLocker recovery key after it has been approved. Generates audit event.

        USE: After intune_approve_action confirms the request_id.

        Args:
            request_id: The request_id from intune_request_bitlocker_key.
        """
        try:
            result = await bitlocker_service.execute_bitlocker_key(request_id)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context=f"BitLocker key execution '{request_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_role_definitions", annotations={**_READ_ANNOTATIONS, "title": "List RBAC Role Definitions"})
    @audited
    async def intune_list_role_definitions(built_in_only: bool = False, top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Intune RBAC role definitions (built-in and custom).

        USE: To understand available roles before auditing assignments.

        Args:
            built_in_only: If True, only return Microsoft built-in roles.
            top: Max results (default 50).
        """
        try:
            result = await rbac_service.list_role_definitions(built_in_only, top)
        except Exception as exc:
            result = graph_error_response(exc, context="list role definitions")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_role_assignments", annotations={**_READ_ANNOTATIONS, "title": "List RBAC Role Assignments"})
    @audited
    async def intune_list_role_assignments(role_definition_id: str | None = None, top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Intune RBAC role assignments with members and scope tags.

        USE: To audit who has which Intune admin role and what scope they cover.

        Args:
            role_definition_id: Filter assignments to a specific role (optional).
            top: Max results (default 50).
        """
        try:
            result = await rbac_service.list_role_assignments(role_definition_id, top)
        except Exception as exc:
            result = graph_error_response(exc, context="list role assignments")
        return render_response(result, response_format)
