"""Business logic: turn raw SAP records into the summary an agent needs.

The equipment master does not hold "last maintenance date" or "assigned technician".
They are derived, and every derived value says where it came from:

  status            equipment flags (deleted / inactive / installed / available)
                    + whether a maintenance order is still open for it
  last maintenance  basic end date of the most recent technically completed (TECO) or
                    closed (CLSD) maintenance order. Production should use actual
                    confirmation dates; see docs/INTEGRATION_SPEC.md.
  technician        person responsible on the most recent order, else the equipment
                    partner in TECHNICIAN_PARTNER_FUNCTIONS (default VW), else the main
                    work centre (a team, not a person)
"""
from __future__ import annotations

import os
import time
from datetime import date

from pydantic import BaseModel

from .sap_client import SapClient, odata_date, safe_key

DONE = ("TECO", "CLSD")


class Technician(BaseModel):
    id: str | None
    kind: str          # person | work_center | none
    source: str


class OpenOrder(BaseModel):
    order: str
    description: str
    planned_start: date | None


class EquipmentSummary(BaseModel):
    equipment: str
    description: str
    status: str
    functional_location: str | None
    functional_location_name: str | None
    maintenance_plant: str | None
    manufacturer: str | None
    serial_number: str | None
    last_maintenance_date: date | None
    last_maintenance_order: str | None
    open_maintenance_order: OpenOrder | None
    assigned_technician: Technician
    source: dict[str, str]


def _is_done(order: dict) -> bool:
    return any(s in (order.get("SystemStatusText") or "").split() for s in DONE)


class EquipmentService:
    def __init__(self, client: SapClient | None = None, cache_seconds: int | None = None):
        self.client = client or SapClient()
        self.cache_seconds = int(os.environ.get("CACHE_SECONDS", 300)) if cache_seconds is None else cache_seconds
        self.partner_functions = [p.strip() for p in os.environ.get("TECHNICIAN_PARTNER_FUNCTIONS", "VW").split(",")]
        self._cache: dict[str, tuple[float, EquipmentSummary]] = {}

    def summary(self, equipment: str) -> EquipmentSummary:
        equipment = safe_key(equipment)
        hit = self._cache.get(equipment)
        if hit and time.monotonic() - hit[0] < self.cache_seconds:
            return hit[1]
        result = self._build(equipment)
        self._cache[equipment] = (time.monotonic(), result)
        return result

    def _build(self, equipment: str) -> EquipmentSummary:
        rows = self.client.query("Equipment", {"Equipment": equipment})
        if not rows:
            raise LookupError(f"equipment {equipment} not found")
        # API_EQUIPMENT keys on (Equipment, ValidityEndDate): one equipment can have several
        # time segments. Use the current one (latest ValidityEndDate, open-ended = 9999-12-31).
        eq = max(rows, key=lambda r: odata_date(r.get("ValidityEndDate")) or date.max)
        orders = self.client.query("MaintenanceOrder", {"Equipment": equipment})
        orders.sort(key=lambda o: odata_date(o.get("MaintOrdBasicStartDate")) or date.min, reverse=True)
        done = [o for o in orders if _is_done(o)]
        open_ = [o for o in orders if not _is_done(o)]
        last = max(done, key=lambda o: odata_date(o.get("MaintOrdBasicEndDate")) or date.min, default=None)

        if eq.get("EquipmentIsMarkedForDeletion"):
            status = "Marked for deletion"
        elif eq.get("EquipmentIsInactive"):
            status = "Inactive"
        elif open_:
            status = "Under maintenance"
        elif eq.get("EquipmentIsInstalled"):
            status = "Installed - in service"
        elif eq.get("EquipmentIsAvailable"):
            status = "Available"
        else:
            status = "Unknown"

        return EquipmentSummary(
            equipment=equipment,
            description=eq.get("EquipmentName") or "",
            status=status,
            functional_location=eq.get("FunctionalLocation") or None,
            functional_location_name=eq.get("FunctionalLocationName") or None,
            maintenance_plant=eq.get("MaintenancePlant") or None,
            manufacturer=eq.get("AssetManufacturerName") or None,
            serial_number=eq.get("ManufacturerSerialNumber") or None,
            last_maintenance_date=odata_date(last.get("MaintOrdBasicEndDate")) if last else None,
            last_maintenance_order=last["MaintenanceOrder"] if last else None,
            open_maintenance_order=OpenOrder(order=open_[0]["MaintenanceOrder"],
                                             description=open_[0].get("MaintenanceOrderDesc") or "",
                                             planned_start=odata_date(open_[0].get("MaintOrdBasicStartDate")))
            if open_ else None,
            assigned_technician=self._technician(equipment, eq, orders),
            source={"equipment": "API_EQUIPMENT/Equipment",
                    "maintenance": "API_MAINTENANCEORDER/MaintenanceOrder",
                    "mode": self.client.mode},
        )

    def _technician(self, equipment: str, eq: dict, orders: list[dict]) -> Technician:
        for o in orders:  # newest first
            if o.get("MaintOrdPersonResponsible"):
                return Technician(id=o["MaintOrdPersonResponsible"], kind="person",
                                  source=f"MaintenanceOrder {o['MaintenanceOrder']} person responsible")
        for p in self.client.query("EquipmentPartner", {"Equipment": equipment}):
            if p.get("PartnerFunction") in self.partner_functions and p.get("Partner"):
                return Technician(id=p["Partner"], kind="person",
                                  source=f"EquipmentPartner function {p['PartnerFunction']}")
        if eq.get("MainWorkCenter"):
            return Technician(id=eq["MainWorkCenter"], kind="work_center", source="Equipment main work centre")
        return Technician(id=None, kind="none", source="not maintained in SAP")
