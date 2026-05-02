from typing import Any
import fastmcp
from mcp_intune.services.device import bulk_action_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_BULK_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_bulk_sync", annotations={**_BULK_ANNOTATIONS, "title": "Bulk Device Sync"})
    @audited
    async def intune_bulk_sync(device_ids: list[str], response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Request sync for multiple managed devices at once (JSON batch, max 20 devices).

        DON'T USE for more than 20 devices — batch into multiple calls.

        Args:
            device_ids: List of Intune managedDeviceId GUIDs (max 20).
        """
        try:
            result = await bulk_action_service.bulk_sync(device_ids)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context="bulk sync")
        return render_response(result, response_format)

    @mcp.tool(name="intune_bulk_restart", annotations={**_BULK_ANNOTATIONS, "title": "Bulk Device Restart"})
    @audited
    async def intune_bulk_restart(device_ids: list[str], response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Request restart for multiple managed devices at once (JSON batch, max 20 devices).

        DON'T USE for more than 20 devices — batch into multiple calls.

        Args:
            device_ids: List of Intune managedDeviceId GUIDs (max 20).
        """
        try:
            result = await bulk_action_service.bulk_restart(device_ids)
        except ValueError as exc:
            result = {"error": str(exc)}
        except Exception as exc:
            result = graph_error_response(exc, context="bulk restart")
        return render_response(result, response_format)
