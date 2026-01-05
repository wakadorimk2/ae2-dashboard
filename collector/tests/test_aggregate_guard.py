import time
import uuid
from fastapi.testclient import TestClient

from app.main import app  # エントリポイントに合わせて調整

client = TestClient(app)

def netid():
    return f"net-test-{uuid.uuid4()}"

def make_headers(api_key: str, ts: float | None = None, nonce: str | None = None):
    return {
        "X-API-Key": api_key,
        "X-Timestamp": str(ts or time.time()),
        "X-Nonce": nonce or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }

def test_aggregate_ok(monkeypatch):
    monkeypatch.setenv("AGGREGATE_API_KEY", "test-key")
    r = client.post("/jobs/aggregate", headers=make_headers("test-key"), json={"network_id": netid()})
    assert r.status_code == 200


def test_missing_api_key(monkeypatch):
    monkeypatch.setenv("AGGREGATE_API_KEY", "test-key")

    r = client.post(
        "/jobs/aggregate",
        headers={"Content-Type": "application/json"},
        json={"network_id": "net-test"},
    )

    assert r.status_code == 401

def test_replayed_nonce(monkeypatch):
    monkeypatch.setenv("AGGREGATE_API_KEY", "test-key")

    nid = netid()
    ts = time.time()
    nonce = str(uuid.uuid4())
    headers = make_headers("test-key", ts=ts, nonce=nonce)

    r1 = client.post("/jobs/aggregate", headers=headers, json={"network_id": nid})
    assert r1.status_code == 200

    r2 = client.post("/jobs/aggregate", headers=headers, json={"network_id": nid})
    assert r2.status_code == 401

def test_rate_limit(monkeypatch):
    monkeypatch.setenv("AGGREGATE_API_KEY", "test-key")

    nid = netid()
    r1 = client.post("/jobs/aggregate", headers=make_headers("test-key"), json={"network_id": nid})
    assert r1.status_code == 200

    r2 = client.post("/jobs/aggregate", headers=make_headers("test-key"), json={"network_id": nid})
    assert r2.status_code == 429