import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from mcp_intune.approval.models import ActionRisk, ApprovalRequest, ApprovalStatus
from mcp_intune.config import settings

_store: dict[str, ApprovalRequest] = {}
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def create_request(
    operation: str,
    device_id: str,
    device_name: str,
    reason: str,
    ticket_id: str,
    risk: str = "high",
    action_params: dict[str, Any] | None = None,
) -> ApprovalRequest:
    req = ApprovalRequest(
        operation=operation,
        device_id=device_id,
        device_name=device_name,
        risk=ActionRisk(risk),
        reason=reason,
        ticket_id=ticket_id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.approval_ttl_seconds),
        action_params=action_params or {},
    )
    async with _get_lock():
        _store[req.request_id] = req
    return req


async def get_request(request_id: str) -> ApprovalRequest | None:
    async with _get_lock():
        return _store.get(request_id)


async def list_pending() -> list[ApprovalRequest]:
    now = datetime.now(timezone.utc)
    async with _get_lock():
        result = []
        for req in _store.values():
            if req.status == ApprovalStatus.PENDING:
                if req.expires_at and req.expires_at < now:
                    req.status = ApprovalStatus.EXPIRED
                else:
                    result.append(req)
        return list(result)


async def decide(request_id: str, approve: bool, comment: str = "") -> ApprovalRequest | None:
    now = datetime.now(timezone.utc)
    async with _get_lock():
        req = _store.get(request_id)
        if req is None:
            return None
        if req.status != ApprovalStatus.PENDING:
            return req
        if req.expires_at and req.expires_at < now:
            req.status = ApprovalStatus.EXPIRED
            return req
        req.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED
        req.decided_at = now
        req.comment = comment
        return req
