import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_bulk_sync_builds_batch_with_correct_requests():
    with patch("mcp_intune.services.device.bulk_action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {
            "responses": [
                {"id": "1", "status": 204, "body": {}},
                {"id": "2", "status": 204, "body": {}},
            ]
        }
        from mcp_intune.services.device.bulk_action_service import bulk_sync
        result = await bulk_sync(["dev-1", "dev-2"])
        assert result["total"] == 2
        batch_body = mock_post.call_args[0][1]
        assert len(batch_body["requests"]) == 2
        assert all(r["method"] == "POST" for r in batch_body["requests"])
        assert all("syncDevice" in r["url"] for r in batch_body["requests"])


@pytest.mark.asyncio
async def test_bulk_sync_rejects_more_than_20_devices():
    from mcp_intune.services.device.bulk_action_service import bulk_sync
    with pytest.raises(ValueError, match="20"):
        await bulk_sync([f"dev-{i}" for i in range(21)])


@pytest.mark.asyncio
async def test_bulk_restart_builds_batch_with_reboot():
    with patch("mcp_intune.services.device.bulk_action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {"responses": [{"id": "1", "status": 204, "body": {}}]}
        from mcp_intune.services.device.bulk_action_service import bulk_restart
        result = await bulk_restart(["dev-1"])
        batch_body = mock_post.call_args[0][1]
        assert "rebootNow" in batch_body["requests"][0]["url"]
