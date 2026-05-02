from typing import Any

import fastmcp

from mcp_intune.services.device import device_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_search_devices", annotations={**_ANNOTATIONS, "title": "Search Intune Devices"})
    @audited
    async def intune_search_devices(
        query: str,
        platform: str | None = None,
        compliance_state: str | None = None,
        top: int | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Search Intune managed devices by device name (prefix), serial number (exact), or UPN (exact).

        USE: Find a device before calling get_device_overview or get_compliance_state.
        DON'T USE: For listing all devices without a query — use export_report instead.

        Args:
            query: Device name prefix, exact serial number, or exact user UPN.
            platform: Optional OS filter — 'Windows', 'iOS', 'Android', 'macOS'.
            compliance_state: Optional filter — 'compliant', 'noncompliant', 'unknown'.
            top: Max results per page (default 50, max 999).
        """
        try:
            result = await device_service.search_devices(query, platform, compliance_state, top)
        except Exception as exc:
            result = graph_error_response(exc, context=f"search '{query}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_device_overview", annotations={**_ANNOTATIONS, "title": "Get Device Overview"})
    @audited
    async def intune_get_device_overview(
        device_id: str,
        include: list[str] | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get a full overview of a managed device including compliance, users, and policies.

        USE: After finding a device_id with intune_search_devices. Call this first for full context.
        DON'T USE: When you only need hardware specs — use intune_get_device_hardware instead.

        Args:
            device_id: Intune managedDeviceId (GUID from search results).
            include: Sections to include — any of ["hardware","primaryUser","compliance","policies","detectedApps"].
                     Omit to include primaryUser and compliance (default).
        """
        try:
            result = await device_service.get_device_overview(device_id, include)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_device_hardware", annotations={**_ANNOTATIONS, "title": "Get Device Hardware"})
    @audited
    async def intune_get_device_hardware(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get hardware inventory for a managed device: model, serial number, storage, RAM.

        USE: When user asks about device specs, storage capacity, or hardware configuration.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_device_hardware(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_device_users", annotations={**_ANNOTATIONS, "title": "Get Device Users"})
    @audited
    async def intune_get_device_users(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get users associated with a managed device (primary user and logged-on users).

        USE: When user asks who owns a device or which users have logged on.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_device_users(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_detected_apps", annotations={**_ANNOTATIONS, "title": "Get Detected Apps"})
    @audited
    async def intune_get_detected_apps(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get all software detected on a managed device (full paginated list).

        USE: When user asks about installed apps, software inventory, or needs to verify if specific software is present.
        Note: May return hundreds of items — consider filtering by name client-side.

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_detected_apps(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_compliance_state", annotations={**_ANNOTATIONS, "title": "Get Compliance State"})
    @audited
    async def intune_get_compliance_state(
        device_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get compliance state and list of failing compliance policies for a managed device.

        USE: When user asks 'why is this device non-compliant?' or needs compliance details.
        Returns device compliance summary AND per-policy states (compliant/nonCompliant/error).

        Args:
            device_id: Intune managedDeviceId (GUID).
        """
        try:
            result = await device_service.get_compliance_state(device_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_policy_status", annotations={**_ANNOTATIONS, "title": "Get Policy Status"})
    @audited
    async def intune_get_policy_status(
        device_id: str,
        policy_type: str | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get configuration policy assignment states for a managed device.

        USE: When user asks 'which configuration policy is failing?', 'what policies are applied to this device?'.
        DON'T USE for compliance policies — use intune_get_compliance_state instead.

        Args:
            device_id: Intune managedDeviceId (GUID).
            policy_type: Optional platform type filter, e.g. 'windows10', 'iOS'.
        """
        try:
            result = await device_service.get_policy_status(device_id, policy_type)
        except Exception as exc:
            result = graph_error_response(exc, context=f"device '{device_id}'")
        return render_response(result, response_format)
