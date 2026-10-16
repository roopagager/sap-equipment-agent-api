# SAP Equipment Agent API

[![tests](https://github.com/roopagager/sap-equipment-agent-api/actions/workflows/tests.yml/badge.svg)](https://github.com/roopagager/sap-equipment-agent-api/actions/workflows/tests.yml)

A FastAPI service that reads **SAP S/4HANA equipment data** through SAP's standard OData APIs (`API_EQUIPMENT`, `API_MAINTENANCEORDER`) and returns one clean JSON summary — **status, functional location, maintenance plant, last maintenance date and assigned technician** — exposed as a tool to an AI agent (Claude tool use and MCP).

Runs offline on sample data shaped exactly like the OData responses, or against the **free SAP Business Accelerator Hub sandbox** with your own API key. The one-page client integration spec is in [docs/INTEGRATION_SPEC.md](docs/INTEGRATION_SPEC.md).

```
Agent (Claude) ──tool──► FastAPI /equipment/{id} ──OData GET──► API_EQUIPMENT  (Equipment, EquipmentPartner)
                          validate · cache · map                  API_MAINTENANCEORDER (MaintenanceOrder)
```

## Quick start
```bash
pip install -r requirements.txt
pytest -q                              # 25 tests
uvicorn app.main:app --reload          # open http://localhost:8000/docs
curl localhost:8000/equipment/10000001
```

```json
{
  "equipment": "10000001",
  "description": "Chiller unit, Building A",
  "status": "Under maintenance",
  "functional_location": "1010-LDN-A-ROOF",
  "maintenance_plant": "1010",
  "last_maintenance_date": "2026-09-08",
  "last_maintenance_order": "4000007",
  "open_maintenance_order": {"order": "4000011", "description": "Compressor high-pressure trip", "planned_start": "2026-10-14"},
  "assigned_technician": {"id": "50001877", "kind": "person", "source": "MaintenanceOrder 4000011 person responsible"},
  "source": {"equipment": "API_EQUIPMENT/Equipment", "maintenance": "API_MAINTENANCEORDER/MaintenanceOrder", "mode": "fixture"}
}
```

## Use the real SAP sandbox
1. Create a free account at <https://api.sap.com>, open **Equipment (API_EQUIPMENT)** and click **Show API Key**.
2. `cp .env.example .env`, set `SAP_MODE=sandbox` and `SAP_API_KEY=...`, and export them.
3. Find real equipment numbers with the API Hub "Try out" page (or `GET .../API_EQUIPMENT/Equipment?$top=5`), then call `/equipment/{id}`.

Sandbox data is SAP's shared demo tenant: many records have no maintenance orders or partners, so `last_maintenance_date` may be `null` and the technician may fall back to the work centre. That is expected and the response says so.

## Connect it to an agent
```bash
export ANTHROPIC_API_KEY=...            # service must be running
python -m agent.claude_agent "What's the status of equipment 10000001 and who is looking after it?"
python -m agent.mcp_server              # or: the same tool over MCP for Claude Desktop
```

## Why the three "derived" fields work the way they do
The equipment master has no "last maintenance date" or "technician" field, so they are derived — and every response says where each value came from:

| Field | Source |
|---|---|
| Status | Equipment flags (deleted / inactive / installed / available) + any open maintenance order |
| Last maintenance date | Basic end date of the latest TECO/CLSD maintenance order (production: confirmation actuals) |
| Technician | Order person responsible → equipment partner (VW) → main work centre (a team) |

## Safety
Read-only GETs only · allow-listed entity sets · equipment numbers validated before reaching an OData `$filter` · retries with backoff and `Retry-After` · 5-minute cache · optional `X-API-Key` on the service · clear 400/404/502 errors, never invented data.

Field names were taken from SAP's published API definitions (SAP Cloud SDK typed clients for `API_EQUIPMENT` and `API_MAINTENANCEORDER`); confirm them against the API Hub for your S/4HANA release.
