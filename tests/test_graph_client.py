import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock, AsyncMock


DEVICE_URL = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices/abc-123"


@pytest.fixture
def mock_token():
    with patch("mcp_intune.graph.client.get_token", return_value="fake-token"):
        yield


# --- _raise_for_status ---

def test_raise_for_status_429_raises_throttling_error():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import ThrottlingError
    response = httpx.Response(429, headers={"Retry-After": "45"}, json={})
    with pytest.raises(ThrottlingError) as exc_info:
        _raise_for_status(response)
    assert exc_info.value.retry_after_seconds == 45


def test_raise_for_status_404_raises_not_found():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import NotFoundError
    response = httpx.Response(404, json={"error": {"message": "Not found"}})
    with pytest.raises(NotFoundError):
        _raise_for_status(response)


def test_raise_for_status_401_raises_auth_error():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import AuthError
    response = httpx.Response(401, json={"error": {"message": "Unauthorized"}})
    with pytest.raises(AuthError):
        _raise_for_status(response)


def test_raise_for_status_500_raises_service_unavailable():
    from mcp_intune.graph.client import _raise_for_status
    from mcp_intune.graph.errors import ServiceUnavailableError
    response = httpx.Response(503, json={})
    with pytest.raises(ServiceUnavailableError):
        _raise_for_status(response)


# --- beta flag ---

def test_beta_api_blocked_when_flag_false():
    from mcp_intune.graph.client import _assert_beta_allowed
    from mcp_intune.graph.errors import BetaApiNotAllowedError
    with pytest.raises(BetaApiNotAllowedError):
        _assert_beta_allowed("/beta/deviceManagement/deviceHealthScripts")


def test_v1_api_always_allowed():
    from mcp_intune.graph.client import _assert_beta_allowed
    _assert_beta_allowed("/v1.0/deviceManagement/managedDevices")  # no exception


# --- graph_get ---

@pytest.mark.asyncio
async def test_graph_get_returns_data(mock_token):
    with respx.mock:
        respx.get(DEVICE_URL).mock(
            return_value=httpx.Response(200, json={"id": "abc-123", "deviceName": "LAP-001"})
        )
        from mcp_intune.graph.client import graph_get
        result = await graph_get("v1.0/deviceManagement/managedDevices/abc-123", ttl=60)
        assert result["id"] == "abc-123"
        assert result["deviceName"] == "LAP-001"


@pytest.mark.asyncio
async def test_graph_get_caches_response(mock_token):
    with respx.mock:
        route = respx.get(DEVICE_URL).mock(
            return_value=httpx.Response(200, json={"id": "abc-123"})
        )
        from mcp_intune.graph.client import graph_get
        await graph_get("v1.0/deviceManagement/managedDevices/abc-123", ttl=60)
        await graph_get("v1.0/deviceManagement/managedDevices/abc-123", ttl=60)
        assert route.call_count == 1  # second call served from cache


@pytest.mark.asyncio
async def test_graph_get_all_pages_follows_next_link(mock_token):
    page1_url = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
    page2_url = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices?$skiptoken=page2"

    with respx.mock:
        # Register more specific route (with query params) first so it matches before the base URL route
        respx.get(page2_url).mock(return_value=httpx.Response(200, json={
            "value": [{"id": "3"}],
        }))
        respx.get(page1_url).mock(return_value=httpx.Response(200, json={
            "value": [{"id": "1"}, {"id": "2"}],
            "@odata.nextLink": page2_url,
        }))
        from mcp_intune.graph.client import graph_get_all_pages
        items = await graph_get_all_pages("v1.0/deviceManagement/managedDevices")
        assert len(items) == 3
        assert [i["id"] for i in items] == ["1", "2", "3"]


# --- build_batch ---

def test_build_batch_accepts_20_requests():
    from mcp_intune.graph.client import build_batch
    requests = [{"id": str(i), "method": "GET", "url": f"/v1.0/test/{i}"} for i in range(20)]
    result = build_batch(requests)
    assert len(result["requests"]) == 20


def test_build_batch_rejects_21_requests():
    from mcp_intune.graph.client import build_batch
    requests = [{"id": str(i), "method": "GET", "url": f"/v1.0/test/{i}"} for i in range(21)]
    with pytest.raises(ValueError, match="20"):
        build_batch(requests)


# --- _do_request with 204 No Content ---

@pytest.mark.asyncio
async def test_do_request_handles_204_no_content(mock_token):
    """Action endpoints like syncDevice return 204 with empty body."""
    with patch("mcp_intune.graph.client._get_http_client") as mock_client_fn:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.url = "https://graph.microsoft.com/v1.0/test"
        mock_client_fn.return_value.request = AsyncMock(return_value=mock_resp)
        from mcp_intune.graph.client import _do_request
        result = await _do_request("POST", "https://graph.microsoft.com/v1.0/test")
        assert result == {}


# --- graph_delete ---

@pytest.mark.asyncio
async def test_graph_delete_calls_delete_method():
    with patch("mcp_intune.graph.client._do_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {}
        from mcp_intune.graph.client import graph_delete
        await graph_delete("v1.0/deviceManagement/managedDevices/abc-123")
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "DELETE"
        assert "abc-123" in call_args[0][1]
