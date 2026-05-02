from datetime import datetime
from pydantic import BaseModel


class DeviceSummary(BaseModel):
    id: str
    deviceName: str | None = None
    serialNumber: str | None = None
    operatingSystem: str | None = None
    osVersion: str | None = None
    complianceState: str | None = None
    lastSyncDateTime: datetime | None = None
    userPrincipalName: str | None = None
    manufacturer: str | None = None
    model: str | None = None


class DetectedApp(BaseModel):
    id: str
    displayName: str | None = None
    version: str | None = None
    publisher: str | None = None
    sizeInByte: int | None = None


class CompliancePolicyState(BaseModel):
    id: str
    displayName: str | None = None
    state: str | None = None
    settingCount: int | None = None
    errorCount: int | None = None
    conflictCount: int | None = None


class ConfigurationState(BaseModel):
    id: str
    displayName: str | None = None
    state: str | None = None
    version: int | None = None
    errorCount: int | None = None
    conflictCount: int | None = None
