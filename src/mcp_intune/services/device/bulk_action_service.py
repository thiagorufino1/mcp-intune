from typing import Any

from mcp_intune.graph.client import build_batch, graph_post

DEVICE_BASE = "/deviceManagement/managedDevices"


def _make_action_requests(device_ids: list[str], action: str, body: dict | None = None) -> list[dict[str, Any]]:
    if len(device_ids) > 20:
        raise ValueError(f"Bulk actions support up to 20 devices at once, got {len(device_ids)}")
    return [
        {
            "id": str(i + 1),
            "method": "POST",
            "url": f"{DEVICE_BASE}/{device_id}/{action}",
            "headers": {"Content-Type": "application/json"},
            "body": body or {},
        }
        for i, device_id in enumerate(device_ids)
    ]


async def bulk_sync(device_ids: list[str]) -> dict[str, Any]:
    requests = _make_action_requests(device_ids, "syncDevice")
    batch = build_batch(requests)
    response = await graph_post("v1.0/$batch", batch)
    responses = response.get("responses", [])
    succeeded = [r for r in responses if r.get("status", 0) in (200, 202, 204)]
    failed = [r for r in responses if r.get("status", 0) not in (200, 202, 204)]
    return {"action": "syncDevice", "total": len(device_ids), "succeeded": len(succeeded), "failed": len(failed), "responses": responses}


async def bulk_restart(device_ids: list[str]) -> dict[str, Any]:
    requests = _make_action_requests(device_ids, "rebootNow")
    batch = build_batch(requests)
    response = await graph_post("v1.0/$batch", batch)
    responses = response.get("responses", [])
    succeeded = [r for r in responses if r.get("status", 0) in (200, 202, 204)]
    failed = [r for r in responses if r.get("status", 0) not in (200, 202, 204)]
    return {"action": "rebootNow", "total": len(device_ids), "succeeded": len(succeeded), "failed": len(failed), "responses": responses}
