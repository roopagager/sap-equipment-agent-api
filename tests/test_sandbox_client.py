"""Sandbox mode without network: a fake session proves URL, headers, $filter, paging and retries."""
import pytest

from app.sap_client import SapClient, SapError


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, queue):
        self.queue, self.calls = queue, []

    def get(self, url, params, headers, timeout):
        self.calls.append((url, dict(params), headers))
        return self.queue.pop(0)


def test_url_headers_filter_paging_retry():
    s = FakeSession([Resp(503, headers={"Retry-After": "0"}),
                     Resp(200, {"d": {"results": [{"Equipment": "1", "__metadata": {}}, {"Equipment": "2"}]}}),
                     Resp(200, {"d": {"results": [{"Equipment": "3"}]}})])
    c = SapClient(mode="sandbox", api_key="k", session=s, page_size=2)
    rows = c.query("MaintenanceOrder", {"Equipment": "10000001"})
    assert [r["Equipment"] for r in rows] == ["1", "2", "3"] and "__metadata" not in rows[0]
    url, params, headers = s.calls[0]
    assert url.endswith("/API_MAINTENANCEORDER/MaintenanceOrder")
    assert params["$filter"] == "Equipment eq '10000001'" and headers["APIKey"] == "k"
    assert s.calls[-1][1]["$skip"] == "2"


def test_bad_key_is_clear_error():
    c = SapClient(mode="sandbox", api_key="wrong", session=FakeSession([Resp(401)]))
    with pytest.raises(SapError, match="API key"):
        c.query("Equipment", {"Equipment": "1"})


def test_sandbox_requires_key(monkeypatch):
    monkeypatch.delenv("SAP_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        SapClient(mode="sandbox", api_key="")


def test_unknown_entity_rejected():
    with pytest.raises(ValueError):
        SapClient(mode="fixture").query("A_JournalEntry")
