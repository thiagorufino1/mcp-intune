from typing import Any
import fastmcp
from mcp_intune.services.updates import update_profile_service, update_ring_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_update_rings", annotations={**_READ_ANNOTATIONS, "title": "List Windows Update Rings"})
    @audited
    async def intune_list_update_rings(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Windows Update for Business (WUfB) update rings with deferral and pause settings.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_ring_service.list_update_rings(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list update rings")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_update_ring", annotations={**_READ_ANNOTATIONS, "title": "Get Update Ring Details"})
    @audited
    async def intune_get_update_ring(ring_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Get a specific update ring with its group assignments.

        Args:
            ring_id: The update ring configuration id (GUID).
        """
        try:
            result = await update_ring_service.get_update_ring(ring_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"get update ring '{ring_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_feature_update_profiles", annotations={**_READ_ANNOTATIONS, "title": "List Feature Update Profiles"})
    @audited
    async def intune_list_feature_update_profiles(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Windows feature update profiles (target Windows version). REQUIRES: ALLOW_BETA_APIS=true.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_profile_service.list_feature_update_profiles(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list feature update profiles")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_quality_update_profiles", annotations={**_READ_ANNOTATIONS, "title": "List Quality Update Profiles"})
    @audited
    async def intune_list_quality_update_profiles(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Windows quality (monthly patch) update profiles. REQUIRES: ALLOW_BETA_APIS=true.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_profile_service.list_quality_update_profiles(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list quality update profiles")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_driver_update_profiles", annotations={**_READ_ANNOTATIONS, "title": "List Driver Update Profiles"})
    @audited
    async def intune_list_driver_update_profiles(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Windows driver update profiles (automated vs manual driver approval). REQUIRES: ALLOW_BETA_APIS=true.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await update_profile_service.list_driver_update_profiles(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list driver update profiles")
        return render_response(result, response_format)
