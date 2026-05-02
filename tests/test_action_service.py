import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_request_sync_calls_graph_post():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_sync
        result = await request_sync("abc-123")
        assert result["action"] == "syncDevice"
        assert result["status"] == "initiated"
        call_path = mock_post.call_args[0][0]
        assert "abc-123" in call_path
        assert "syncDevice" in call_path


@pytest.mark.asyncio
async def test_request_restart_calls_graph_post():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_restart
        result = await request_restart("abc-123")
        assert result["action"] == "rebootNow"
        assert result["status"] == "initiated"
        call_path = mock_post.call_args[0][0]
        assert "rebootNow" in call_path


@pytest.mark.asyncio
async def test_request_scan_sends_quick_scan_flag():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_scan
        result = await request_scan("abc-123", quick_scan=True)
        assert result["action"] == "windowsDefenderScan"
        body = mock_post.call_args[0][1]
        assert body.get("quickScan") is True


@pytest.mark.asyncio
async def test_request_locate_calls_graph_post():
    with patch("mcp_intune.services.device.action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.action_service import request_locate
        result = await request_locate("abc-123")
        assert result["action"] == "locateDevice"
        call_path = mock_post.call_args[0][0]
        assert "locateDevice" in call_path
