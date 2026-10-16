"""Read-only client for SAP S/4HANA OData V2 APIs used by the equipment service.

Modes (SAP_MODE):
  fixture  - offline sample data in fixtures/, shaped like real OData V2 responses (default)
  sandbox  - SAP Business Accelerator Hub sandbox, needs SAP_API_KEY from api.sap.com

Service and entity names are the standard S/4HANA Cloud APIs:
  API_EQUIPMENT/Equipment, API_EQUIPMENT/EquipmentPartner, API_MAINTENANCEORDER/MaintenanceOrder
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ENTITIES = {
    "Equipment": "API_EQUIPMENT",
    "EquipmentPartner": "API_EQUIPMENT",
    "MaintenanceOrder": "API_MAINTENANCEORDER",
}
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SANDBOX_URL = "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap"
_SAFE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
_ODATA_DATE = re.compile(r"/Date\((-?\d+)(?:[+-]\d+)?\)/")


class SapError(RuntimeError):
    pass


def safe_key(value: str) -> str:
    """Only plain SAP keys reach an OData $filter - blocks query injection from tool inputs."""
    if not isinstance(value, str) or not _SAFE.match(value):
        raise ValueError(f"invalid SAP key: {value!r}")
    return value


def odata_date(value) -> date | None:
    """Convert OData V2 '/Date(1700000000000)/' to a date. Returns None for empty values."""
    if not value:
        return None
    m = _ODATA_DATE.match(str(value))
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date()


class SapClient:
    def __init__(self, mode: str | None = None, api_key: str | None = None, base_url: str | None = None,
                 session=None, page_size: int = 100, max_retries: int = 3, timeout: float = 20):
        self.mode = (mode or os.environ.get("SAP_MODE", "fixture")).lower()
        self.api_key = api_key if api_key is not None else os.environ.get("SAP_API_KEY", "")
        self.base_url = (base_url or os.environ.get("SAP_BASE_URL", SANDBOX_URL)).rstrip("/")
        self.session = session or requests.Session()
        self.page_size, self.max_retries, self.timeout = page_size, max_retries, timeout
        if self.mode not in ("fixture", "sandbox"):
            raise ValueError("SAP_MODE must be 'fixture' or 'sandbox'")
        if self.mode == "sandbox" and not self.api_key:
            raise RuntimeError("SAP_MODE=sandbox needs SAP_API_KEY (api.sap.com > Show API Key)")

    def query(self, entity: str, filters: dict[str, str] | None = None,
              select: list[str] | None = None, limit: int = 200) -> list[dict]:
        if entity not in ENTITIES:
            raise ValueError(f"entity not allowed: {entity}")
        filters = {k: safe_key(v) for k, v in (filters or {}).items()}
        if self.mode == "fixture":
            rows = json.loads((FIXTURES / f"{entity}.json").read_text())["d"]["results"]
            rows = [{k: v for k, v in r.items() if k != "__metadata"} for r in rows
                    if all(str(r.get(k)) == v for k, v in filters.items())]
            return [{k: r.get(k) for k in select} for r in rows][:limit] if select else rows[:limit]
        return self._odata(entity, filters, select, limit)

    def _odata(self, entity, filters, select, limit):
        url = f"{self.base_url}/{ENTITIES[entity]}/{entity}"
        params = {"$format": "json", "$top": str(min(self.page_size, limit)), "$skip": "0"}
        if filters:
            params["$filter"] = " and ".join(f"{k} eq '{v}'" for k, v in filters.items())
        if select:
            params["$select"] = ",".join(select)
        rows: list[dict] = []
        while len(rows) < limit:
            page = self._get(url, params)["d"]["results"]
            for r in page:
                r.pop("__metadata", None)
            rows += page
            if len(page) < int(params["$top"]):
                break
            params["$skip"] = str(int(params["$skip"]) + len(page))
        return rows[:limit]

    def _get(self, url, params):
        headers = {"APIKey": self.api_key, "Accept": "application/json"}
        for attempt in range(self.max_retries + 1):
            r = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                time.sleep(min(float(r.headers.get("Retry-After", 2 ** attempt)), 20))
                continue
            if r.status_code == 401:
                raise SapError("SAP rejected the API key (401) - check SAP_API_KEY")
            if r.status_code >= 400:
                raise SapError(f"SAP returned HTTP {r.status_code}")
            return r.json()
        raise SapError("SAP did not respond after retries")
