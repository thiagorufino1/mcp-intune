import uuid
from typing import Any
from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    source: str = "graph"
    api_version: str = "v1.0"
    cached: bool = False
    next_cursor: str | None = None


class ToolResponse(BaseModel):
    status: str
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data: Any = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)

    @classmethod
    def ok(cls, data: Any, **meta_kwargs: Any) -> "ToolResponse":
        return cls(status="ok", data=data, meta=ResponseMeta(**meta_kwargs))

    @classmethod
    def error(cls, errors: list[str], **meta_kwargs: Any) -> "ToolResponse":
        return cls(status="error", errors=errors, meta=ResponseMeta(**meta_kwargs))
