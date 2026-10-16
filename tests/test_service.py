from datetime import date

import pytest

from app.sap_client import SapClient, odata_date, safe_key
from app.service import EquipmentService


@pytest.fixture
def svc():
    return EquipmentService(SapClient(mode="fixture"), cache_seconds=60)


def test_equipment_with_open_order(svc):
    s = svc.summary("10000001")
    assert s.functional_location == "1010-LDN-A-ROOF" and s.maintenance_plant == "1010"
    assert s.status == "Under maintenance"
    assert s.open_maintenance_order.order == "4000011"


def test_last_maintenance_is_latest_completed_order(svc):
    s = svc.summary("10000001")
    assert s.last_maintenance_date == date(2026, 9, 8) and s.last_maintenance_order == "4000007"


def test_technician_from_latest_order(svc):
    t = svc.summary("10000001").assigned_technician
    assert t.id == "50001877" and t.kind == "person" and "4000011" in t.source


def test_technician_falls_back_to_equipment_partner(svc):
    t = svc.summary("10000002").assigned_technician
    assert t.id == "50002201" and "EquipmentPartner" in t.source


def test_technician_falls_back_to_work_centre(svc):
    s = svc.summary("10000003")
    assert s.status == "Inactive" and s.last_maintenance_date is None
    assert s.assigned_technician.kind == "work_center" and s.assigned_technician.id == "MECH-01"


def test_installed_no_open_order(svc):
    assert svc.summary("10000002").status == "Installed - in service"


def test_not_found(svc):
    with pytest.raises(LookupError):
        svc.summary("99999999")


@pytest.mark.parametrize("bad", ["1' or '1'='1", "../etc", "", "x" * 50])
def test_injection_rejected(bad):
    with pytest.raises(ValueError):
        safe_key(bad)


def test_cache_avoids_second_sap_call():
    calls = []

    class Counting(SapClient):
        def query(self, entity, *a, **k):
            calls.append(entity)
            return super().query(entity, *a, **k)

    svc = EquipmentService(Counting(mode="fixture"), cache_seconds=60)
    svc.summary("10000001"); n = len(calls); svc.summary("10000001")
    assert len(calls) == n


def test_odata_date_parsing():
    assert odata_date("/Date(1788825600000)/") == date(2026, 9, 8)
    assert odata_date(None) is None and odata_date("") is None
