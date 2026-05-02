from typing import Any

from mcp_intune.graph.client import graph_get, graph_get_paged

FEATURE_BASE = "beta/deviceManagement/windowsFeatureUpdateProfiles"
QUALITY_BASE = "beta/deviceManagement/windowsQualityUpdateProfiles"
DRIVER_BASE = "beta/deviceManagement/windowsDriverUpdateProfiles"


async def list_feature_update_profiles(top: int | None = None) -> dict[str, Any]:
    params = {"$select": "id,displayName,description,featureUpdateVersion,deployableContentDisplayName,endOfSupportDate"}
    return await graph_get_paged(FEATURE_BASE, params=params, top=top)


async def get_feature_update_profile(profile_id: str) -> dict[str, Any]:
    return await graph_get(f"{FEATURE_BASE}/{profile_id}", ttl=120)


async def list_quality_update_profiles(top: int | None = None) -> dict[str, Any]:
    params = {"$select": "id,displayName,description,releaseDateDisplayName"}
    return await graph_get_paged(QUALITY_BASE, params=params, top=top)


async def get_quality_update_profile(profile_id: str) -> dict[str, Any]:
    return await graph_get(f"{QUALITY_BASE}/{profile_id}", ttl=120)


async def list_driver_update_profiles(top: int | None = None) -> dict[str, Any]:
    params = {"$select": "id,displayName,description,approvalType,deploymentDeferralInDays"}
    return await graph_get_paged(DRIVER_BASE, params=params, top=top)


async def get_driver_update_profile(profile_id: str) -> dict[str, Any]:
    return await graph_get(f"{DRIVER_BASE}/{profile_id}", ttl=120)
