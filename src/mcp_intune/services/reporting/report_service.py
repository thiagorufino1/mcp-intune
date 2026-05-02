from typing import Any

from mcp_intune.graph.client import graph_get, graph_post

REPORTS_BASE = "v1.0/deviceManagement/reports"

VALID_REPORTS = [
    "Devices", "DevicesWithInventory", "ActiveMalware", "AllAppsList",
    "AppInstallStatusAggregate", "ComanagedDeviceWorkloads", "CompliancePolicyStatuses",
    "ConfigurationPolicyStatuses", "DeviceComplianceTrend", "NonCompliantDeviceAndSettings",
    "PolicyNonComplianceSummary", "PolicyNonComplianceDetail", "Remediations",
    "RemediationDeviceStatus", "FeatureUpdatePolicyFailuresAggregate",
    "FeatureUpdateDeviceState", "QualityUpdateDeviceState", "QualityUpdatePolicyStatusCounts",
]


async def export_report(
    report_name: str,
    filter: str | None = None,
    select: list[str] | None = None,
    format: str = "csv",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "reportName": report_name,
        "format": format,
        "localizationType": "localizedValuesAsAdditionalColumn",
    }
    if filter:
        body["filter"] = filter
    if select:
        body["select"] = select
    result = await graph_post(f"{REPORTS_BASE}/exportJobs", body)
    return {
        "jobId": result.get("id"),
        "status": result.get("status"),
        "reportName": result.get("reportName"),
        "downloadUrl": result.get("url"),
        "expiresDateTime": result.get("expirationDateTime"),
    }


async def get_report_status(job_id: str) -> dict[str, Any]:
    result = await graph_get(f"{REPORTS_BASE}/exportJobs/{job_id}", ttl=10)
    return {
        "jobId": result.get("id"),
        "status": result.get("status"),
        "reportName": result.get("reportName"),
        "downloadUrl": result.get("url"),
        "expiresDateTime": result.get("expirationDateTime"),
    }


def list_report_catalog() -> list[str]:
    return VALID_REPORTS
