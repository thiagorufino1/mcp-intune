import os
# Set env vars before any module imports settings singleton
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("FASTMCP_TRANSPORT", "http")
os.environ.setdefault("ALLOW_BETA_APIS", "false")
os.environ.setdefault("GRAPH_MAX_RETRIES", "1")  # 1 attempt = no retries, speeds up error tests

import pytest


@pytest.fixture(autouse=True)
def clear_graph_cache():
    # Defensive import: graph.client doesn't exist until Task 5
    try:
        from mcp_intune.graph.client import clear_cache
        clear_cache()
    except ImportError:
        pass
    yield
    try:
        from mcp_intune.graph.client import clear_cache
        clear_cache()
    except ImportError:
        pass
