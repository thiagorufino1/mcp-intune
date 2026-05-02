import json
from enum import Enum
from typing import Any


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


def render_response(data: Any, response_format: ResponseFormat) -> str:
    if response_format == ResponseFormat.JSON:
        if hasattr(data, "model_dump"):
            return json.dumps(data.model_dump(), default=str, indent=2)
        return json.dumps(data, default=str, indent=2)
    if hasattr(data, "model_dump"):
        return _dict_to_markdown(data.model_dump())
    if isinstance(data, dict):
        return _dict_to_markdown(data)
    if isinstance(data, list):
        return "\n\n".join(_dict_to_markdown(item) if isinstance(item, dict) else str(item) for item in data[:20])
    return str(data)


def _dict_to_markdown(d: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    for key, value in d.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}:**")
            lines.append(_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}:** ({len(value)} items)")
            for item in value[:10]:
                if isinstance(item, dict):
                    lines.append(_dict_to_markdown(item, indent + 1))
                    lines.append("")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}**{key}:** {value}")
    return "\n".join(lines)
