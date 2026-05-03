from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

AUTOPATCH_BASE = "v1.0/admin/windows/updates"


async def list_deployments(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(f"{AUTOPATCH_BASE}/deployments", top=top)


async def get_deployment(deployment_id: str) -> dict[str, Any]:
    return await graph_get(f"{AUTOPATCH_BASE}/deployments/{deployment_id}", ttl=60)


async def list_updatable_assets(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(f"{AUTOPATCH_BASE}/updatableAssets", top=top)


# TODO: expose as intune_list_catalog_entries tool
async def list_catalog_entries(top: int | None = None) -> dict[str, Any]:
    return await graph_get_paged(f"{AUTOPATCH_BASE}/catalog/entries", top=top)
