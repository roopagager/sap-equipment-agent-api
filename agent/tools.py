"""The FastAPI endpoint, exposed as an agent tool.

The agent never talks to SAP directly: it calls our endpoint, which validates input,
caches, and returns a small, typed JSON summary. Tool output is data, not instructions.
"""
from __future__ import annotations

import json
import os

import httpx

GET_EQUIPMENT_STATUS = {
    "name": "get_equipment_status",
    "description": (
        "Look up an SAP equipment record by its equipment number. Returns status, functional location, "
        "maintenance plant, last maintenance date, any open maintenance order and the assigned technician, "
        "with the SAP source of each value. Read-only. Use when the user asks about an asset's condition, "
        "location, maintenance history or who looks after it."),
    "input_schema": {
        "type": "object",
        "properties": {"equipment_id": {"type": "string", "description": "SAP equipment number, e.g. 10000001"}},
        "required": ["equipment_id"],
    },
}
TOOLS = [GET_EQUIPMENT_STATUS]


def run_tool(name: str, tool_input: dict, http: httpx.Client | None = None) -> str:
    """Execute a tool call by calling the FastAPI service. Always returns a JSON string."""
    if name != "get_equipment_status":
        return json.dumps({"error": f"unknown tool {name}"})
    base = os.environ.get("EQUIPMENT_API_URL", "http://localhost:8000")
    headers = {"X-API-Key": os.environ["SERVICE_API_KEY"]} if os.environ.get("SERVICE_API_KEY") else {}
    client = http or httpx.Client(base_url=base, timeout=30)
    try:
        r = client.get(f"/equipment/{tool_input.get('equipment_id', '')}", headers=headers)
    except httpx.HTTPError as e:
        return json.dumps({"error": f"equipment service unreachable: {e}"})
    if r.status_code != 200:
        return json.dumps({"error": r.json().get("detail", f"HTTP {r.status_code}")})
    return r.text
