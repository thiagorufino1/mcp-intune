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


@pytest.mark.asyncio
async def test_request_retire_creates_pending_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.device.destructive_action_service import request_retire
    result = await request_retire("dev-1", "LAP-001", "Security", "INC-001")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "retire"
    assert "request_id" in result


@pytest.mark.asyncio
async def test_request_wipe_creates_pending_approval_with_params():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.device.destructive_action_service import request_wipe
    result = await request_wipe("dev-2", "LAP-002", "Lost device", "INC-002", keep_enrollment_data=False)
    assert result["status"] == "pending_approval"
    assert result["operation"] == "wipe"
    req = store._store[result["request_id"]]
    assert req.action_params.get("keepEnrollmentData") is False


@pytest.mark.asyncio
async def test_execute_approved_action_calls_retire():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request("retire", "dev-3", "LAP-003", "Test", "INC-003", "medium")
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.device.destructive_action_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.destructive_action_service import execute_approved_action
        result = await execute_approved_action(req.request_id)
        assert result["executed"] == "retire"
        assert "dev-3" in mock_post.call_args[0][0]


@pytest.mark.asyncio
async def test_execute_approved_action_raises_if_not_approved():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request("wipe", "dev-4", "LAP-004", "Test", "INC-004", "high")
    from mcp_intune.services.device.destructive_action_service import execute_approved_action
    with pytest.raises(ValueError, match="not approved"):
        await execute_approved_action(req.request_id)


@pytest.mark.asyncio
async def test_execute_approved_action_calls_run_remediation():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        "run_remediation", "dev-5", "LAP-005", "Fix issue", "INC-005", "medium",
        action_params={"scriptId": "rem-1"},
    )
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.scripts.remediation_service.graph_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {}
        from mcp_intune.services.device.destructive_action_service import execute_approved_action
        result = await execute_approved_action(req.request_id)
        assert result["executed"] == "run_remediation"
        mock_post.assert_called_once()
        call_path = mock_post.call_args[0][0]
        assert "initiateOnDemandProactiveRemediation" in call_path
        assert "dev-5" in call_path


@pytest.mark.asyncio
async def test_execute_approved_action_raises_for_unknown_operation():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        "unknown_op", "dev-6", "LAP-006", "Test", "INC-006", "high",
    )
    await store.decide(req.request_id, approve=True)
    from mcp_intune.services.device.destructive_action_service import execute_approved_action
    with pytest.raises(ValueError, match="Unknown operation"):
        await execute_approved_action(req.request_id)
