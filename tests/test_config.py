def test_settings_loads_from_env():
    from mcp_intune.config import settings
    assert settings.azure_tenant_id == "test-tenant-id"
    assert settings.azure_client_id == "test-client-id"
    assert settings.azure_client_secret.get_secret_value() == "test-client-secret"
    assert settings.allow_beta_apis is False
    assert settings.graph_default_top == 50
    assert settings.cache_ttl_device == 60
