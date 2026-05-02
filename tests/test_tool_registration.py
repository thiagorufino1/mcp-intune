from typing import Any


class FakeMCP:
    """Minimal FastMCP stub for registration tests."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, name: str, annotations: dict | None = None):
        def decorator(fn: Any) -> Any:
            self.tools[name] = fn
            return fn
        return decorator


EXPECTED_TOOLS = [
    "intune_search_devices",
    "intune_get_device_overview",
    "intune_get_device_hardware",
    "intune_get_device_users",
    "intune_get_detected_apps",
    "intune_get_compliance_state",
    "intune_get_policy_status",
]


def test_all_device_tools_registered():
    from mcp_intune.tools.device.device_tools import _register
    fake = FakeMCP()
    _register(fake)
    for tool_name in EXPECTED_TOOLS:
        assert tool_name in fake.tools, f"Tool '{tool_name}' not registered"


def test_no_extra_tools_registered():
    from mcp_intune.tools.device.device_tools import _register
    fake = FakeMCP()
    _register(fake)
    assert len(fake.tools) == len(EXPECTED_TOOLS), (
        f"Expected {len(EXPECTED_TOOLS)} tools, got {len(fake.tools)}: {list(fake.tools)}"
    )


def test_all_tools_have_intune_prefix():
    from mcp_intune.tools.device.device_tools import _register
    fake = FakeMCP()
    _register(fake)
    for name in fake.tools:
        assert name.startswith("intune_"), f"Tool '{name}' missing 'intune_' prefix"


def test_action_tools_registered():
    class FakeMCP:
        def __init__(self):
            self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator

    fake = FakeMCP()
    from mcp_intune.tools.device.action_tools import _register
    _register(fake)
    expected = {
        "intune_request_sync", "intune_request_restart", "intune_request_scan",
        "intune_request_locate", "intune_request_retire", "intune_request_wipe",
        "intune_request_delete", "intune_list_pending_actions",
        "intune_approve_action", "intune_deny_action", "intune_execute_action",
    }
    assert expected.issubset(fake.tools.keys())
