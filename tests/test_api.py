import pytest
from fastapi.testclient import TestClient

from audit.serve import app

pytestmark = pytest.mark.integration

client = TestClient(app)


def test_index_and_results():
    assert "Grader Audit" in client.get("/").text
    r = client.get("/api/results").json()
    assert r["meta"]["n_cases"] == 96
    assert set(r["summary"]) == {"naive", "hardened"}


def test_case_view_has_diff_for_tables():
    c = client.get("/api/case/T4_revenue_by_region/partial").json()
    assert c["gold"] and c["output"] and c["instruction"]
    assert len(c["diff"]["only_in_output"]) == 1
    assert client.get("/api/case/A1_null_customer_ids/gold").json()["diff"] is None
    assert client.get("/api/case/nope/gold").status_code == 404


def test_report_endpoints():
    assert "<table>" in client.get("/api/report").json()["html"]
    r = client.get("/report.md")
    assert r.headers["content-disposition"].startswith("attachment")
    assert "Not affiliated with HUD" in r.text
