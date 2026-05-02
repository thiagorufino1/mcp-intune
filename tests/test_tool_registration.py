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


def test_reporting_tools_registered():
    class FakeMCP:
        def __init__(self):
            self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator

    fake = FakeMCP()
    from mcp_intune.tools.reporting.reporting_tools import _register
    _register(fake)
    expected = {
        "intune_export_report", "intune_get_report_status", "intune_list_report_catalog",
        "intune_get_audit_events", "intune_get_endpoint_analytics",
    }
    assert expected.issubset(fake.tools.keys())


def test_scripts_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.scripts.scripts_tools import _register
    _register(fake)
    expected = {"intune_list_remediations", "intune_get_remediation_run_state", "intune_request_remediation_run"}
    assert expected.issubset(fake.tools.keys())


def test_updates_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.updates.updates_tools import _register
    _register(fake)
    expected = {
        "intune_list_update_rings", "intune_get_update_ring",
        "intune_list_feature_update_profiles", "intune_list_quality_update_profiles",
        "intune_list_driver_update_profiles",
    }
    assert expected.issubset(fake.tools.keys())


def test_autopilot_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.autopilot.autopilot_tools import _register
    _register(fake)
    expected = {"intune_list_autopilot_devices", "intune_get_autopilot_device_by_serial", "intune_import_autopilot_device"}
    assert expected.issubset(fake.tools.keys())


def test_governance_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.governance.governance_tools import _register
    _register(fake)
    expected = {
        "intune_get_laps_metadata", "intune_request_laps_secret", "intune_execute_laps_secret",
        "intune_find_bitlocker_keys", "intune_request_bitlocker_key", "intune_execute_bitlocker_key",
        "intune_list_role_definitions", "intune_list_role_assignments",
    }
    assert expected.issubset(fake.tools.keys())


def test_autopatch_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.autopatch.autopatch_tools import _register
    _register(fake)
    expected = {"intune_list_autopatch_deployments", "intune_get_autopatch_deployment", "intune_list_updatable_assets"}
    assert expected.issubset(fake.tools.keys())


def test_bulk_tools_registered():
    class FakeMCP:
        def __init__(self): self.tools = {}
        def tool(self, name=None, annotations=None):
            def decorator(fn):
                self.tools[name] = fn
                return fn
            return decorator
    fake = FakeMCP()
    from mcp_intune.tools.device.bulk_tools import _register
    _register(fake)
    expected = {"intune_bulk_sync", "intune_bulk_restart"}
    assert expected.issubset(fake.tools.keys())
