import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from agent import claude_agent
from agent.tools import TOOLS, run_tool
from app import main
from app.sap_client import SapClient, SapError
from app.service import EquipmentService


@pytest.fixture(autouse=True)
def fresh_service(monkeypatch):
    monkeypatch.setattr(main, "_service", EquipmentService(SapClient(mode="fixture"), cache_seconds=0))
    monkeypatch.delenv("SERVICE_API_KEY", raising=False)


@pytest.fixture
def http():
    return TestClient(main.app)


def test_endpoint_returns_structured_json(http):
    r = http.get("/equipment/10000001")
    body = r.json()
    assert r.status_code == 200
    assert {"status", "last_maintenance_date", "assigned_technician", "functional_location",
            "maintenance_plant", "source"} <= body.keys()
    assert body["last_maintenance_date"] == "2026-09-08"


def test_endpoint_errors(http):
    assert http.get("/equipment/99999999").status_code == 404
    assert http.get("/equipment/bad'key").status_code == 400


def test_sap_outage_is_502(http, monkeypatch):
    def boom(*a, **k):
        raise SapError("timeout")
    monkeypatch.setattr(main._service.client, "query", boom)
    assert http.get("/equipment/10000001").status_code == 502


def test_service_key_enforced(http, monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY", "s3cret")
    assert http.get("/equipment/10000001").status_code == 401
    assert http.get("/equipment/10000001", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_tool_calls_endpoint(http):
    out = json.loads(run_tool("get_equipment_status", {"equipment_id": "10000002"}, http))
    assert out["assigned_technician"]["id"] == "50002201"
    assert "error" in json.loads(run_tool("get_equipment_status", {"equipment_id": "99999999"}, http))


def test_tool_schema():
    assert TOOLS[0]["input_schema"]["required"] == ["equipment_id"]


def test_agent_loop_runs_tool_then_answers(http):
    """Fake Claude: first asks for the tool, then answers using the tool result."""
    seen = {}

    class FakeMessages:
        def __init__(self):
            self.n = 0

        def create(self, **kw):
            self.n += 1
            if self.n == 1:
                return NS(stop_reason="tool_use", content=[
                    NS(type="tool_use", id="tu_1", name="get_equipment_status", input={"equipment_id": "10000001"})])
            result = kw["messages"][-1]["content"][0]
            seen["result"] = json.loads(result["content"])
            assert result["tool_use_id"] == "tu_1"
            return NS(stop_reason="end_turn", content=[NS(type="text", text=f"Status: {seen['result']['status']}")])

    answer = claude_agent.ask("status of 10000001?", client=NS(messages=FakeMessages()), model="test", http=http)
    assert answer == "Status: Under maintenance"


@pytest.mark.anyio
async def test_mcp_server_exposes_tool():
    from mcp import Client
    from agent import mcp_server
    async with Client(mcp_server.mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert names == {"get_equipment_status"}


@pytest.fixture
def anyio_backend():
    return "asyncio"
