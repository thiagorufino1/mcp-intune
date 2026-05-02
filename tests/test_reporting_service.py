import pytest
from unittest.mock import AsyncMock, patch


EXPORT_JOB_STUB = {
    "id": "job-abc-123",
    "status": "notStarted",
    "reportName": "Devices",
    "url": None,
    "expirationDateTime": None,
}

AUDIT_EVENTS_STUB = {
    "value": [
        {
            "id": "evt-1",
            "displayName": "Update managed device",
            "category": "Device",
            "activityType": "Patch ManagedDevice",
            "activityDateTime": "2026-05-01T10:00:00Z",
            "actor": {"userPrincipalName": "admin@empresa.com"},
            "resources": [],
        }
    ]
}


@pytest.mark.asyncio
async def test_export_report_creates_export_job():
    with patch("mcp_intune.services.reporting.report_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = EXPORT_JOB_STUB
        from mcp_intune.services.reporting.report_service import export_report
        result = await export_report("Devices")
        assert result["jobId"] == "job-abc-123"
        assert result["status"] == "notStarted"
        body = mock_post.call_args[0][1]
        assert body["reportName"] == "Devices"
        assert body["format"] == "csv"


@pytest.mark.asyncio
async def test_export_report_passes_filter():
    with patch("mcp_intune.services.reporting.report_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = EXPORT_JOB_STUB
        from mcp_intune.services.reporting.report_service import export_report
        await export_report("Devices", filter="(Platform eq 'Windows')")
        body = mock_post.call_args[0][1]
        assert "Windows" in body.get("filter", "")


@pytest.mark.asyncio
async def test_get_report_status_calls_graph_get():
    with patch("mcp_intune.services.reporting.report_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {**EXPORT_JOB_STUB, "status": "completed", "url": "https://example.com/report.csv"}
        from mcp_intune.services.reporting.report_service import get_report_status
        result = await get_report_status("job-abc-123")
        assert result["status"] == "completed"
        assert "job-abc-123" in mock_get.call_args[0][0]


@pytest.mark.asyncio
async def test_get_audit_events_returns_events():
    with patch("mcp_intune.services.reporting.audit_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AUDIT_EVENTS_STUB
        from mcp_intune.services.reporting.audit_service import get_audit_events
        result = await get_audit_events(days=7)
        assert result["count"] == 1
        assert result["auditEvents"][0]["category"] == "Device"
        call_params = mock_get.call_args[1].get("params") or mock_get.call_args[0][1]
        assert "activityDateTime" in str(call_params)


@pytest.mark.asyncio
async def test_get_audit_events_with_actor_filter():
    with patch("mcp_intune.services.reporting.audit_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = AUDIT_EVENTS_STUB
        from mcp_intune.services.reporting.audit_service import get_audit_events
        await get_audit_events(days=7, actor_upn="admin@empresa.com")
        call_params = str(mock_get.call_args)
        assert "admin@empresa.com" in call_params
