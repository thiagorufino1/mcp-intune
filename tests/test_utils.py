import json
import pytest
from mcp_intune.utils.render import ResponseFormat, render_response
from mcp_intune.utils.graph_errors import graph_error_response
from mcp_intune.graph.errors import ThrottlingError, NotFoundError, BetaApiNotAllowedError


# --- render ---

def test_render_response_json_returns_valid_json():
    data = {"id": "123", "deviceName": "LAP-001", "count": 5}
    result = render_response(data, ResponseFormat.JSON)
    parsed = json.loads(result)
    assert parsed["id"] == "123"


def test_render_response_markdown_returns_string():
    data = {"id": "123", "deviceName": "LAP-001"}
    result = render_response(data, ResponseFormat.MARKDOWN)
    assert isinstance(result, str)
    assert "LAP-001" in result


def test_render_response_markdown_skips_none_values():
    data = {"id": "123", "emptyField": None, "deviceName": "LAP-001"}
    result = render_response(data, ResponseFormat.MARKDOWN)
    assert "emptyField" not in result


# --- graph_error_response ---

def test_graph_error_response_not_found():
    exc = NotFoundError("not found")
    result = graph_error_response(exc, context="device 'abc'")
    assert result["status"] == "error"
    assert "not found" in result["errors"][0].lower()


def test_graph_error_response_throttling():
    exc = ThrottlingError("throttled", retry_after_seconds=30)
    result = graph_error_response(exc, context="search")
    assert result["status"] == "error"
    assert "30" in result["errors"][0]


def test_graph_error_response_beta_not_allowed():
    exc = BetaApiNotAllowedError("/beta/test")
    result = graph_error_response(exc)
    assert result["status"] == "error"


# --- @audited decorator ---

@pytest.mark.asyncio
async def test_audited_decorator_passes_through_result():
    from mcp_intune.utils.audit import audited

    @audited
    async def my_tool(device_id: str) -> str:
        return f"result for {device_id}"

    result = await my_tool(device_id="abc-123")
    assert result == "result for abc-123"


@pytest.mark.asyncio
async def test_audited_decorator_re_raises_exceptions():
    from mcp_intune.utils.audit import audited

    @audited
    async def failing_tool() -> str:
        raise ValueError("something went wrong")

    with pytest.raises(ValueError, match="something went wrong"):
        await failing_tool()


@pytest.mark.asyncio
async def test_audited_sets_trace_id():
    from mcp_intune.utils.audit import audited, get_trace_id

    captured_trace_id: list[str] = []

    @audited
    async def my_tool() -> str:
        captured_trace_id.append(get_trace_id())
        return "ok"

    await my_tool()
    assert len(captured_trace_id[0]) == 8
