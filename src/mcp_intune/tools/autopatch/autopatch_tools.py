from typing import Any
import fastmcp
from mcp_intune.services.autopatch import autopatch_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_list_autopatch_deployments", annotations={**_READ_ANNOTATIONS, "title": "List Autopatch Deployments"})
    @audited
    async def intune_list_autopatch_deployments(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List Windows Autopatch deployments from the Windows Update for Business deployment service.

        REQUIRES: WindowsUpdates.Read.All permission.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await autopatch_service.list_deployments(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list Autopatch deployments")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_autopatch_deployment", annotations={**_READ_ANNOTATIONS, "title": "Get Autopatch Deployment"})
    @audited
    async def intune_get_autopatch_deployment(deployment_id: str, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """Get details of a specific Windows Autopatch deployment.

        Args:
            deployment_id: The deployment id (GUID from intune_list_autopatch_deployments).
        """
        try:
            result = await autopatch_service.get_deployment(deployment_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"get Autopatch deployment '{deployment_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_updatable_assets", annotations={**_READ_ANNOTATIONS, "title": "List Updatable Assets"})
    @audited
    async def intune_list_updatable_assets(top: int | None = None, response_format: ResponseFormat = ResponseFormat.MARKDOWN) -> str:
        """List devices registered as updatable assets in Windows Autopatch.

        REQUIRES: WindowsUpdates.Read.All permission.

        Args:
            top: Max results (default 50).
        """
        try:
            result = await autopatch_service.list_updatable_assets(top)
        except Exception as exc:
            result = graph_error_response(exc, context="list updatable assets")
        return render_response(result, response_format)
