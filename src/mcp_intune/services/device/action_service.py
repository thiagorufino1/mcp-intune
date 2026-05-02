from typing import Any

from mcp_intune.graph.client import graph_post

DEVICE_BASE = "v1.0/deviceManagement/managedDevices"


async def request_sync(device_id: str) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/syncDevice", {})
    return {"action": "syncDevice", "device_id": device_id, "status": "initiated"}


async def request_restart(device_id: str) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/rebootNow", {})
    return {"action": "rebootNow", "device_id": device_id, "status": "initiated"}


async def request_scan(device_id: str, quick_scan: bool = True) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/windowsDefenderScan", {"quickScan": quick_scan})
    return {"action": "windowsDefenderScan", "device_id": device_id, "quickScan": quick_scan, "status": "initiated"}


async def request_locate(device_id: str) -> dict[str, Any]:
    await graph_post(f"{DEVICE_BASE}/{device_id}/locateDevice", {})
    return {"action": "locateDevice", "device_id": device_id, "status": "initiated"}
