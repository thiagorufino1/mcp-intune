from datetime import datetime, timedelta, timezone
from typing import Any

from mcp_intune.graph.client import graph_get

AUDIT_BASE = "v1.0/deviceManagement/auditEvents"


async def get_audit_events(
    days: int = 7,
    actor_upn: str | None = None,
    category: str | None = None,
    top: int = 50,
) -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_parts = [f"activityDateTime gt {since}"]
    if actor_upn:
        safe_upn = actor_upn.replace("'", "''")
        filter_parts.append(f"actor/userPrincipalName eq '{safe_upn}'")
    if category:
        safe_category = category.replace("'", "''")
        filter_parts.append(f"category eq '{safe_category}'")
    params = {
        "$filter": " and ".join(filter_parts),
        "$orderby": "activityDateTime desc",
        "$top": top,
        "$select": "id,displayName,category,activityType,activityDateTime,actor,resources",
    }
    result = await graph_get(AUDIT_BASE, params=params, ttl=60)
    events = result.get("value", [])
    return {"auditEvents": events, "count": len(events)}
