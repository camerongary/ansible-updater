import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scripts.web_server as ws

# Use Flask test client
ws.app.testing = True


@pytest.fixture
def client():
    with ws.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_body(client):
    resp = client.get("/health")
    assert resp.get_json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# /api/results
# ---------------------------------------------------------------------------

def test_api_results_empty(client, monkeypatch):
    monkeypatch.setattr(ws, "load_results", lambda: [])
    resp = client.get("/api/results")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_results_returns_all_hosts(client, monkeypatch, sample_results):
    monkeypatch.setattr(ws, "load_results", lambda: sample_results)
    resp = client.get("/api/results")
    data = resp.get_json()
    assert len(data) == 3
    assert {h["hostname"] for h in data} == {"web-01", "db-01", "monitor-01"}


# ---------------------------------------------------------------------------
# /api/stats
# ---------------------------------------------------------------------------

def test_api_stats_empty(client, monkeypatch):
    monkeypatch.setattr(ws, "load_results", lambda: [])
    resp = client.get("/api/stats")
    data = resp.get_json()
    assert data["total_hosts"] == 0
    assert data["total_updates"] == 0
    assert data["total_security"] == 0
    assert data["hosts_needing_reboot"] == 0


def test_api_stats_aggregates_correctly(client, monkeypatch, sample_results):
    monkeypatch.setattr(ws, "load_results", lambda: sample_results)
    resp = client.get("/api/stats")
    data = resp.get_json()
    assert data["total_hosts"] == 3
    assert data["total_updates"] == 8    # 5 + 3 + 0
    assert data["total_security"] == 3   # 2 + 1 + 0
    assert data["hosts_needing_reboot"] == 1
    assert "last_updated" in data


# ---------------------------------------------------------------------------
# / (dashboard)
# ---------------------------------------------------------------------------

def test_index_returns_200(client, monkeypatch):
    monkeypatch.setattr(ws, "load_results", lambda: [])
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_shows_hostnames(client, monkeypatch, sample_results):
    monkeypatch.setattr(ws, "load_results", lambda: sample_results)
    html = client.get("/").data.decode()
    assert "web-01" in html
    assert "db-01" in html
    assert "monitor-01" in html


def test_index_no_hosts_message(client, monkeypatch):
    monkeypatch.setattr(ws, "load_results", lambda: [])
    html = client.get("/").data.decode()
    assert "No hosts have been scanned yet" in html


def test_index_shows_reboot_status(client, monkeypatch, sample_results):
    monkeypatch.setattr(ws, "load_results", lambda: sample_results)
    html = client.get("/").data.decode()
    assert "Yes" in html   # db-01 needs reboot
    assert "No" in html


def test_index_shows_update_interval(client, monkeypatch, sample_results):
    monkeypatch.setenv("UPDATE_INTERVAL", "7200")
    monkeypatch.setattr(ws, "load_results", lambda: sample_results)
    html = client.get("/").data.decode()
    assert "7200" in html


# ---------------------------------------------------------------------------
# load_results
# ---------------------------------------------------------------------------

def test_load_results_reads_files(reports_dir, monkeypatch):
    monkeypatch.setattr(ws, "REPORTS_DIR", str(reports_dir))
    results = ws.load_results()
    assert len(results) == 3


def test_load_results_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "REPORTS_DIR", str(tmp_path))
    assert ws.load_results() == []


def test_load_results_ignores_bad_json(tmp_path, monkeypatch):
    (tmp_path / "broken_update_result.json").write_text("{bad json")
    (tmp_path / "ok_update_result.json").write_text('{"hostname": "fine"}')
    monkeypatch.setattr(ws, "REPORTS_DIR", str(tmp_path))
    results = ws.load_results()
    assert len(results) == 1
    assert results[0]["hostname"] == "fine"
