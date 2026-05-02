import asyncio
from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

UPDATE_RINGS_BASE = "v1.0/deviceManagement/deviceConfigurations"
WUB_FILTER = "isof('microsoft.graph.windowsUpdateForBusinessConfiguration')"


async def list_update_rings(top: int | None = None) -> dict[str, Any]:
    params = {
        "$filter": WUB_FILTER,
        "$select": "id,displayName,description,qualityUpdatesDeferralPeriodInDays,featureUpdatesDeferralPeriodInDays,qualityUpdatesPaused,featureUpdatesPaused,businessReadyUpdatesOnly",
    }
    return await graph_get_paged(UPDATE_RINGS_BASE, params=params, top=top)


async def get_update_ring(ring_id: str) -> dict[str, Any]:
    ring, assignments = await asyncio.gather(
        graph_get(f"{UPDATE_RINGS_BASE}/{ring_id}", ttl=120),
        graph_get(f"{UPDATE_RINGS_BASE}/{ring_id}/assignments", ttl=120),
    )
    return {
        "ring": ring,
        "assignments": assignments.get("value", []),
    }
