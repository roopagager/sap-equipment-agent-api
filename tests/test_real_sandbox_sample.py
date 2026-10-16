"""Replays real responses captured from the SAP Business Accelerator Hub sandbox.

fixtures/sandbox_samples/ holds what API_EQUIPMENT and API_MAINTENANCEORDER actually returned
for equipment 10001883 (a cooling water pump in plant 1010), trimmed to the fields we use.
"""
from datetime import date

from app import sap_client
from app.sap_client import SapClient
from app.service import EquipmentService


def test_real_sandbox_pump(monkeypatch):
    monkeypatch.setattr(sap_client, "FIXTURES", sap_client.FIXTURES / "sandbox_samples")
    s = EquipmentService(SapClient(mode="fixture"), cache_seconds=0).summary("10001883")
    assert s.functional_location == "A1010-CWS-WCS"
    assert s.maintenance_plant == "1010"
    # 25 real orders: latest TECO/CLSD is 4000241, basic end 2022-08-18
    assert s.last_maintenance_date == date(2022, 8, 18)
    assert s.last_maintenance_order == "4000241"
    # two orders were never completed (CRTD); the newest open one is reported
    assert s.status == "Under maintenance"
    assert s.open_maintenance_order.order == "4000124"
    # no person responsible and no partners in the sandbox -> work centre
    assert s.assigned_technician.kind == "work_center"
    assert s.assigned_technician.id == "AMS-100"
