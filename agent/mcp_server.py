"""The same tool over MCP, for Claude Desktop or any MCP host.

    python -m agent.mcp_server      (stdio; calls the FastAPI service at EQUIPMENT_API_URL)
"""
from __future__ import annotations

import json

from mcp.server import MCPServer

from .tools import run_tool

mcp = MCPServer("SAP Equipment")


@mcp.tool()
def get_equipment_status(equipment_id: str) -> dict:
    """Look up SAP equipment: status, functional location, maintenance plant, last maintenance date,
    open maintenance order and assigned technician. Read-only."""
    return json.loads(run_tool("get_equipment_status", {"equipment_id": equipment_id}))


if __name__ == "__main__":
    mcp.run()
