import pytest
from unittest.mock import AsyncMock, patch


LAPS_METADATA_STUB = {
    "id": "cred-1",
    "deviceName": "LAP-001",
    "refreshDateTime": "2026-05-01T08:00:00Z",
    "credentials": [
        {
            "backupDateTime": "2026-05-01T08:00:00Z",
            "accountName": "Administrator",
        }
    ],
}


@pytest.mark.asyncio
async def test_get_laps_metadata_calls_correct_endpoint():
    with patch("mcp_intune.services.governance.laps_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = LAPS_METADATA_STUB
        from mcp_intune.services.governance.laps_service import get_laps_metadata
        result = await get_laps_metadata("dev-abc")
        assert result["deviceName"] == "LAP-001"
        call_path = mock_get.call_args[0][0]
        assert "dev-abc" in call_path
        assert "deviceLocalCredentialInfo" in call_path


@pytest.mark.asyncio
async def test_request_laps_secret_creates_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.governance.laps_service import request_laps_secret
    result = await request_laps_secret("dev-abc", "LAP-001", "Admin recovery", "INC-001")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "laps_secret"
    assert result["risk"] == "high"


@pytest.mark.asyncio
async def test_execute_laps_secret_calls_graph_with_select_credentials():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        "laps_secret", "dev-abc", "LAP-001", "Test", "INC-001", "high",
        action_params={"device_id": "dev-abc"},
    )
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.governance.laps_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {**LAPS_METADATA_STUB, "credentials": [{"accountName": "Administrator", "password": "SecretP@ss1"}]}
        from mcp_intune.services.governance.laps_service import execute_laps_secret
        result = await execute_laps_secret(req.request_id)
        assert result["credentials"] is not None
        call_params = str(mock_get.call_args)
        assert "$select" in call_params or "credentials" in call_params


@pytest.mark.asyncio
async def test_execute_laps_secret_raises_if_not_approved():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request("laps_secret", "dev-abc", "LAP-001", "Test", "INC-002", "high")
    from mcp_intune.services.governance.laps_service import execute_laps_secret
    with pytest.raises(ValueError, match="not approved"):
        await execute_laps_secret(req.request_id)


BITLOCKER_KEYS_STUB = {
    "value": [
        {
            "id": "bk-1",
            "createdDateTime": "2026-01-01T00:00:00Z",
            "volumeType": "operatingSystemVolume",
            "deviceId": "aad-device-1",
        }
    ]
}


@pytest.mark.asyncio
async def test_find_bitlocker_keys_calls_correct_endpoint():
    with patch("mcp_intune.services.governance.bitlocker_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = BITLOCKER_KEYS_STUB
        from mcp_intune.services.governance.bitlocker_service import find_bitlocker_keys
        result = await find_bitlocker_keys(device_id="aad-device-1")
        assert result["value"][0]["volumeType"] == "operatingSystemVolume"
        call_path = mock_get.call_args[0][0]
        assert "bitlocker" in call_path.lower() or "recoveryKeys" in call_path


@pytest.mark.asyncio
async def test_request_bitlocker_key_creates_approval():
    from mcp_intune.approval import store
    store._store.clear()
    from mcp_intune.services.governance.bitlocker_service import request_bitlocker_key
    result = await request_bitlocker_key("bk-1", "LAP-001", "Drive recovery", "INC-002")
    assert result["status"] == "pending_approval"
    assert result["operation"] == "bitlocker_key"
    assert result["risk"] == "high"


@pytest.mark.asyncio
async def test_execute_bitlocker_key_fetches_key_with_select():
    from mcp_intune.approval import store
    store._store.clear()
    req = await store.create_request(
        "bitlocker_key", "bk-1", "LAP-001", "Test", "INC-003", "high",
        action_params={"key_id": "bk-1"},
    )
    await store.decide(req.request_id, approve=True)
    with patch("mcp_intune.services.governance.bitlocker_service.graph_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"id": "bk-1", "key": "123456-789012-345678-901234-567890-123456-789012-345678"}
        from mcp_intune.services.governance.bitlocker_service import execute_bitlocker_key
        result = await execute_bitlocker_key(req.request_id)
        assert "key" in result
        call_params = str(mock_get.call_args)
        assert "key" in call_params
