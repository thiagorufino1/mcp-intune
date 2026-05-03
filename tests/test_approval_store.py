import pytest


@pytest.mark.asyncio
async def test_create_request_returns_pending():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        operation="wipe",
        device_id="dev-1",
        device_name="LAP-001",
        reason="Security incident",
        ticket_id="INC-001",
        risk="high",
    )
    from mcp_intune.approval.models import ApprovalStatus
    assert req.status == ApprovalStatus.PENDING
    assert req.operation == "wipe"
    assert req.request_id in store._store


@pytest.mark.asyncio
async def test_list_pending_returns_only_pending():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        operation="retire", device_id="d1", device_name="LAP-002",
        reason="Test", ticket_id="INC-002", risk="medium",
    )
    pending = await store.list_pending()
    assert any(r.request_id == req.request_id for r in pending)


@pytest.mark.asyncio
async def test_decide_approve_changes_status():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    store._store.clear()
    req = await store.create_request(
        operation="wipe", device_id="d2", device_name="LAP-003",
        reason="Test", ticket_id="INC-003", risk="high",
    )
    result = await store.decide(req.request_id, approve=True, comment="Approved")
    assert result.status == ApprovalStatus.APPROVED
    assert result.comment == "Approved"


@pytest.mark.asyncio
async def test_decide_deny_changes_status():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    store._store.clear()
    req = await store.create_request(
        operation="wipe", device_id="d3", device_name="LAP-004",
        reason="Test", ticket_id="INC-004", risk="high",
    )
    result = await store.decide(req.request_id, approve=False, comment="Denied")
    assert result.status == ApprovalStatus.DENIED


@pytest.mark.asyncio
async def test_get_request_returns_none_for_unknown():
    from mcp_intune.approval import store
    result = await store.get_request("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_pending_marks_expired_requests():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    from datetime import datetime, timezone, timedelta
    store._store.clear()
    req = await store.create_request(
        "wipe", "dev-exp", "LAP-EXP", "Test expiry", "INC-EXP", "high",
    )
    # Force expiry by backdating expires_at
    store._store[req.request_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    pending = await store.list_pending()
    assert not any(r.request_id == req.request_id for r in pending)
    assert store._store[req.request_id].status == ApprovalStatus.EXPIRED


@pytest.mark.asyncio
async def test_decide_on_expired_request_returns_expired_status():
    from mcp_intune.approval import store
    from mcp_intune.approval.models import ApprovalStatus
    from datetime import datetime, timezone, timedelta
    store._store.clear()
    req = await store.create_request(
        "retire", "dev-exp2", "LAP-EXP2", "Test", "INC-EXP2", "medium",
    )
    store._store[req.request_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    result = await store.decide(req.request_id, approve=True, comment="Too late")
    assert result.status == ApprovalStatus.EXPIRED
    # Should NOT have been approved
    assert result.status != ApprovalStatus.APPROVED
