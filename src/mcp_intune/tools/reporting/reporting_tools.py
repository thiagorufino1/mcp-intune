from typing import Any

import fastmcp

from mcp_intune.services.reporting import analytics_service, audit_service, report_service
from mcp_intune.utils.audit import audited
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.utils.render import ResponseFormat, render_response

_READ_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
_WRITE_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}


def _register(mcp: fastmcp.FastMCP) -> None:

    @mcp.tool(name="intune_export_report", annotations={**_WRITE_ANNOTATIONS, "title": "Export Intune Report"})
    @audited
    async def intune_export_report(
        report_name: str,
        filter: str | None = None,
        select: list[str] | None = None,
        format: str = "csv",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Create an Intune report export job. Returns jobId to poll with intune_get_report_status.

        USE: For bulk device/compliance/app data exports. Call intune_list_report_catalog first.
        DON'T USE for real-time queries — use device tools instead.

        Args:
            report_name: Report identifier (e.g. 'Devices', 'CompliancePolicyStatuses').
            filter: OData filter string (e.g. "(Platform eq 'Windows')").
            select: Column names to include (e.g. ["DeviceName", "ComplianceState"]).
            format: Export format — 'csv' (default) or 'json'.
        """
        try:
            result = await report_service.export_report(report_name, filter, select, format)
        except Exception as exc:
            result = graph_error_response(exc, context=f"export report '{report_name}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_report_status", annotations={**_READ_ANNOTATIONS, "title": "Get Report Export Status"})
    @audited
    async def intune_get_report_status(
        job_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Check status of a report export job. When status is 'completed', downloadUrl is available.

        USE: After intune_export_report. Poll until status changes to 'completed' or 'failed'.

        Args:
            job_id: The jobId returned by intune_export_report.
        """
        try:
            result = await report_service.get_report_status(job_id)
        except Exception as exc:
            result = graph_error_response(exc, context=f"report status '{job_id}'")
        return render_response(result, response_format)

    @mcp.tool(name="intune_list_report_catalog", annotations={**_READ_ANNOTATIONS, "title": "List Available Reports"})
    @audited
    async def intune_list_report_catalog(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List all available Intune report names for use with intune_export_report.

        USE: When unsure which report_name to use in intune_export_report.
        """
        try:
            catalog = report_service.list_report_catalog()
            result = {"reports": catalog, "count": len(catalog)}
        except Exception as exc:
            result = graph_error_response(exc, context="list report catalog")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_audit_events", annotations={**_READ_ANNOTATIONS, "title": "Get Audit Events"})
    @audited
    async def intune_get_audit_events(
        days: int = 7,
        actor_upn: str | None = None,
        category: str | None = None,
        top: int = 50,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get Intune audit events (who did what, when).

        USE: For change tracking, incident investigation, or compliance audits.

        Args:
            days: How many days back to fetch (default 7, max 30 recommended).
            actor_upn: Filter by the UPN of the admin who made changes.
            category: Filter by category e.g. 'Device', 'DeviceConfiguration', 'CompliancePolicy'.
            top: Max number of events to return (default 50).
        """
        try:
            result = await audit_service.get_audit_events(days, actor_upn, category, top)
        except Exception as exc:
            result = graph_error_response(exc, context="get audit events")
        return render_response(result, response_format)

    @mcp.tool(name="intune_get_endpoint_analytics", annotations={**_READ_ANNOTATIONS, "title": "Get Endpoint Analytics"})
    @audited
    async def intune_get_endpoint_analytics(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get Endpoint Analytics overview scores for the tenant (startup performance, app reliability, etc).

        USE: For fleet health overview. Scores range 0-100, higher is better.
        """
        try:
            result = await analytics_service.get_endpoint_analytics_summary()
        except Exception as exc:
            result = graph_error_response(exc, context="get endpoint analytics")
        return render_response(result, response_format)
