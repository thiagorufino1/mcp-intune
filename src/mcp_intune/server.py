import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import fastmcp
import structlog

from mcp_intune.graph.client import _get_http_client
from mcp_intune.logging_config import configure_logging
from mcp_intune.tools.device import device_tools, action_tools, bulk_tools
from mcp_intune.tools.reporting import reporting_tools
from mcp_intune.tools.scripts import scripts_tools
from mcp_intune.tools.updates import updates_tools
from mcp_intune.tools.autopilot import autopilot_tools
from mcp_intune.tools.governance import governance_tools
from mcp_intune.tools.autopatch import autopatch_tools

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def _lifespan(server: fastmcp.FastMCP) -> AsyncGenerator[None, None]:
    logger.info("server_starting", transport=os.getenv("FASTMCP_TRANSPORT", "http"))
    yield
    client = _get_http_client()
    try:
        await client.aclose()
    except Exception as exc:
        logger.warning("http_client_close_error", error=str(exc))
    logger.info("server_stopped")


mcp = fastmcp.FastMCP("mcp-intune", lifespan=_lifespan)
device_tools._register(mcp)
action_tools._register(mcp)
bulk_tools._register(mcp)
reporting_tools._register(mcp)
scripts_tools._register(mcp)
updates_tools._register(mcp)
autopilot_tools._register(mcp)
governance_tools._register(mcp)
autopatch_tools._register(mcp)


def main() -> None:
    transport = os.getenv("FASTMCP_TRANSPORT", "http")
    host = os.getenv("FASTMCP_HOST", "127.0.0.1")
    port = int(os.getenv("FASTMCP_PORT", "8000"))
    if transport == "http":
        mcp.run(transport=transport, host=host, port=port)
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
