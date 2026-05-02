from typing import Any

from mcp_intune.graph.client import graph_get

ANALYTICS_OVERVIEW = "v1.0/deviceManagement/userExperienceAnalyticsOverview"


async def get_endpoint_analytics_summary() -> dict[str, Any]:
    return await graph_get(ANALYTICS_OVERVIEW, ttl=300)
