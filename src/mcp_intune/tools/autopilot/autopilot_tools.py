from typing import Any
import fastmcp
from mcp_intune.services.autopilot import autopilot_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_WRITE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_autopilot_devices", annotations={**_READ_ANNOTATIONS, "title": "List Autopilot Devices"})
    @audited
    async def intune_list_autopilot_devices(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Windows Autopilot device identities registered in the tenant.

        USE: To see enrolled Autopilot devices, serial numbers, and profile assignment status.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await autopilot_service.list_autopilot_devices(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list autopilot devices")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_autopilot_device_by_serial", annotations={**_READ_ANNOTATIONS, "title": "Get Autopilot Device by Serial"})
    @audited
    async def intune_get_autopilot_device_by_serial(serial_number: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Find a specific Autopilot device identity by serial number.

        USE: Before importing a device, to check if it's already registered.

        Args:
            serial_number: Device serial number (exact match).
        """
        try:
            device = await autopilot_service.get_autopilot_device_by_serial(serial_number)
            result = device if device is not None else {"found": False, "serial_number": serial_number}
        except Exception as exc:
            result = graph_error_response(exc, context=f"get autopilot device '{serial_number}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_import_autopilot_device", annotations={**_WRITE_ANNOTATIONS, "title": "Import Autopilot Device"})
    @audited
    async def intune_import_autopilot_device(serial_number: str, hardware_hash: str, group_tag: str | None = None, assigned_user_principal_name: str | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Import a new device into Windows Autopilot using hardware hash.

        NOTE: Hardware hash must be obtained from the device using Get-WindowsAutoPilotInfo.

        Args:
            serial_number: Device serial number.
            hardware_hash: Base64 hardware hash from Get-WindowsAutoPilotInfo.
            group_tag: Optional Autopilot group tag for profile targeting.
            assigned_user_principal_name: Optional UPN to pre-assign the device.
        """
        try:
            result = await autopilot_service.import_autopilot_device(serial_number, hardware_hash, group_tag, assigned_user_principal_name)
        except Exception as exc:
            result = graph_error_response(exc, context=f"import autopilot device '{serial_number}'")
        return render_response(result, response_format)
