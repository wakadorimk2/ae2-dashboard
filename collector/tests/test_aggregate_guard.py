import time
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app  # エントリポイントに合わせて調整

client = TestClient(app)

def patch_aggregate_storage(monkeypatch):
    # Avoid 503 due to missing GCS_BUCKET and skip real GCS I/O in guard tests.
    monkeypatch.setattr("app.routes.settings.GCS_BUCKET", "test-bucket")

    def fake_load_json_from_gcs(object_name: str):
        if object_name.endswith("latest.json"):
            return {"entries_path": "raw/entries.json", "ts": time.time()}
        return {"entries": []}

    monkeypatch.setattr("app.routes.load_json_from_gcs", fake_load_json_from_gcs)
    monkeypatch.setattr(
        "app.routes.save_json_to_gcs",
        lambda payload, object_name: f"gs://test-bucket/{object_name}",
    )

def netid():
    return f"net-test-{uuid.uuid4()}"

def api_key():
    return f"test-key-{uuid.uuid4()}"

def make_headers(api_key: str, ts: float | None = None, nonce: str | None = None):
    return {
        "X-API-Key": api_key,
        "X-Timestamp": str(ts or time.time()),
        "X-Nonce": nonce or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }

def test_aggregate_ok(monkeypatch):
    key = api_key()
    monkeypatch.setenv("AGGREGATE_API_KEY", key)
    patch_aggregate_storage(monkeypatch)
    r = client.post("/jobs/aggregate", headers=make_headers(key), json={"network_id": netid()})
    assert r.status_code == 200


def test_missing_api_key(monkeypatch):
    key = api_key()
    monkeypatch.setenv("AGGREGATE_API_KEY", key)
    patch_aggregate_storage(monkeypatch)

    r = client.post(
        "/jobs/aggregate",
        headers={"Content-Type": "application/json"},
        json={"network_id": "net-test"},
    )

    assert r.status_code == 401

def test_replayed_nonce(monkeypatch):
    key = api_key()
    monkeypatch.setenv("AGGREGATE_API_KEY", key)
    patch_aggregate_storage(monkeypatch)

    nid = netid()
    ts = time.time()
    nonce = str(uuid.uuid4())
    headers = make_headers(key, ts=ts, nonce=nonce)

    r1 = client.post("/jobs/aggregate", headers=headers, json={"network_id": nid})
    assert r1.status_code == 200

    headers = make_headers(key, ts=time.time(), nonce=nonce)
    r2 = client.post("/jobs/aggregate", headers=headers, json={"network_id": nid})
    assert r2.status_code == 401

def test_rate_limit(monkeypatch):
    key = api_key()
    monkeypatch.setenv("AGGREGATE_API_KEY", key)
    patch_aggregate_storage(monkeypatch)

    r1 = client.post("/jobs/aggregate", headers=make_headers(key), json={"network_id": netid()})
    assert r1.status_code == 200

    r2 = client.post("/jobs/aggregate", headers=make_headers(key), json={"network_id": netid()})
    assert r2.status_code == 429

@pytest.mark.parametrize("bad_ts", ["NaN", "inf"])
def test_invalid_timestamp_non_finite(monkeypatch, bad_ts):
    key = api_key()
    monkeypatch.setenv("AGGREGATE_API_KEY", key)
    patch_aggregate_storage(monkeypatch)

    headers = make_headers(key)
    headers["X-Timestamp"] = bad_ts
    r = client.post("/jobs/aggregate", headers=headers, json={"network_id": netid()})
    assert r.status_code == 401
