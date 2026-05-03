import asyncio
from typing import Any

from mcp_intune.config import settings
from mcp_intune.graph.client import graph_get, graph_get_all_pages, graph_get_paged

DEVICE_BASE = "v1.0/deviceManagement/managedDevices"

HARDWARE_SELECT = ",".join([
    "id", "deviceName", "manufacturer", "model", "serialNumber",
    "totalStorageSpaceInBytes", "freeStorageSpaceInBytes",
    "physicalMemoryInBytes", "operatingSystem", "osVersion",
])

OVERVIEW_SELECT = ",".join([
    "id", "deviceName", "manufacturer", "model", "serialNumber",
    "operatingSystem", "osVersion", "complianceState",
    "lastSyncDateTime", "userPrincipalName", "managementState",
    "enrolledDateTime", "deviceEnrollmentType", "azureADDeviceId",
    "managedDeviceOwnerType",
])


async def search_devices(
    query: str,
    platform: str | None = None,
    compliance_state: str | None = None,
    top: int | None = None,
) -> dict[str, Any]:
    safe_query = query.replace("'", "''")  # OData single-quote escaping
    filter_parts = [
        f"(startswith(deviceName,'{safe_query}') or serialNumber eq '{safe_query}' or userPrincipalName eq '{safe_query}')"
    ]
    if platform:
        filter_parts.append(f"operatingSystem eq '{platform}'")
    if compliance_state:
        filter_parts.append(f"complianceState eq '{compliance_state}'")

    params = {
        "$filter": " and ".join(filter_parts),
        "$select": "id,deviceName,serialNumber,operatingSystem,osVersion,complianceState,lastSyncDateTime,userPrincipalName,manufacturer,model",
    }
    return await graph_get_paged(DEVICE_BASE, params=params, top=top)


async def get_device_overview(device_id: str, include: list[str] | None = None) -> dict[str, Any]:
    include = include or []
    device = await graph_get(
        f"{DEVICE_BASE}/{device_id}",
        params={"$select": OVERVIEW_SELECT},
        ttl=settings.cache_ttl_device,
    )

    coroutines: dict[str, Any] = {}
    if not include or "primaryUser" in include:
        coroutines["users"] = graph_get(f"{DEVICE_BASE}/{device_id}/users", ttl=settings.cache_ttl_device)
    if not include or "compliance" in include:
        coroutines["compliance_states"] = graph_get(
            f"{DEVICE_BASE}/{device_id}/deviceCompliancePolicyStates",
            ttl=settings.cache_ttl_policy,
        )
    if "policies" in include:
        coroutines["config_states"] = graph_get(
            f"{DEVICE_BASE}/{device_id}/deviceConfigurationStates",
            ttl=settings.cache_ttl_policy,
        )
    if "detectedApps" in include:
        coroutines["detected_apps"] = graph_get_all_pages(f"{DEVICE_BASE}/{device_id}/detectedApps")

    extras: dict[str, Any] = {}
    if coroutines:
        resolved = await asyncio.gather(*coroutines.values(), return_exceptions=True)
        for key, result in zip(coroutines.keys(), resolved):
            extras[key] = {"error": str(result)} if isinstance(result, Exception) else result

    return {"device": device, **extras}


async def get_device_hardware(device_id: str) -> dict[str, Any]:
    return await graph_get(
        f"{DEVICE_BASE}/{device_id}",
        params={"$select": HARDWARE_SELECT},
        ttl=settings.cache_ttl_device,
    )


async def get_device_users(device_id: str) -> dict[str, Any]:
    return await graph_get(f"{DEVICE_BASE}/{device_id}/users", ttl=settings.cache_ttl_device)


async def get_detected_apps(device_id: str) -> list[Any]:
    return await graph_get_all_pages(f"{DEVICE_BASE}/{device_id}/detectedApps")


async def get_compliance_state(device_id: str) -> dict[str, Any]:
    device, policy_states = await asyncio.gather(
        graph_get(
            f"{DEVICE_BASE}/{device_id}",
            params={"$select": "id,deviceName,complianceState,lastSyncDateTime,userPrincipalName"},
            ttl=settings.cache_ttl_device,
        ),
        graph_get(
            f"{DEVICE_BASE}/{device_id}/deviceCompliancePolicyStates",
            ttl=settings.cache_ttl_policy,
        ),
    )
    return {
        "device": device,
        "compliancePolicyStates": policy_states.get("value", []),
    }


async def get_policy_status(device_id: str, policy_type: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if policy_type:
        safe_policy_type = policy_type.replace("'", "''")
        params["$filter"] = f"platformType eq '{safe_policy_type}'"

    result = await graph_get(
        f"{DEVICE_BASE}/{device_id}/deviceConfigurationStates",
        params=params or None,
        ttl=settings.cache_ttl_policy,
    )
    return {"configurationStates": result.get("value", [])}
