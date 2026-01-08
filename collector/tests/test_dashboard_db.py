import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import _build_dashboard_from_db_rows, _compute_growth_per_min

client = TestClient(app)


def test_compute_growth_per_min_missing_prev():
    assert _compute_growth_per_min(10, 100.0, None, None) == 0.0


def test_compute_growth_per_min_non_positive_dt():
    assert _compute_growth_per_min(10, 100.0, 5, 100.0) == 0.0
    assert _compute_growth_per_min(10, 100.0, 5, 120.0) == 0.0


@pytest.mark.parametrize(
    ("latest", "prev", "expected"),
    [
        (20, 10, 10.0),
        (5, 10, -5.0),
    ],
)
def test_compute_growth_per_min_signed(latest, prev, expected):
    assert _compute_growth_per_min(latest, 100.0, prev, 40.0) == expected


def test_compute_growth_per_min_dt_guard(monkeypatch):
    monkeypatch.setattr("app.routes.settings.MIN_DT_SEC", 60)
    assert _compute_growth_per_min(10, 100.0, 5, 95.5) == 0.0


def test_dashboard_db_response_shape(monkeypatch):
    rows = [
        ("item", "minecraft:stone", 100, 100.0, 40, 40.0),
        ("fluid", "minecraft:water", 20, 100.0, 50, 40.0),
        ("gas", "mod:gas", 5, 100.0, None, None),
    ]
    monkeypatch.setattr("app.routes.load_inventory_latest_with_prev", lambda world_id: rows)

    res = client.get("/dashboard?world_id=atm9&top_n=2")
    assert res.status_code == 200
    data = res.json()

    assert data["source"] == "db"
    assert data["world_id"] == "atm9"
    assert data["rows"] == 3
    note = data.get("note")
    assert isinstance(note, dict)
    assert note.get("dt_guard_count") == 0

    assert isinstance(data.get("top_amount"), list)
    top = data.get("top")
    assert isinstance(top, dict)
    for metric in ("amount", "growth_per_min", "decrease_per_min"):
        assert isinstance(top.get(metric), dict)
        for kind in ("item", "fluid", "gas"):
            assert isinstance(top[metric].get(kind), list)

    item_entries = data["top"]["amount"]["item"]
    assert item_entries
    first_item = item_entries[0]
    assert first_item["growth_per_min"] == pytest.approx(60.0)
    assert first_item["delta"] == 60
    assert first_item["dt_sec"] == pytest.approx(60.0)
    assert first_item["decrease_per_min"] == 0
    assert "top_amount_items" in data
    assert isinstance(data["top_amount_items"][0].get("growth_per_min"), float)


def test_dashboard_world_alias(monkeypatch):
    rows = [
        ("item", "minecraft:stone", 1, 100.0, None, None),
    ]
    monkeypatch.setattr("app.routes.load_inventory_latest_with_prev", lambda world_id: rows)

    res = client.get("/dashboard?world=foo")
    assert res.status_code == 200
    data = res.json()
    assert data["world_id"] == "foo"
    assert data["source"] == "db"


def test_build_dashboard_dt_guard(monkeypatch):
    monkeypatch.setattr("app.routes.settings.MIN_DT_SEC", 60)
    rows = [
        ("item", "minecraft:stone", 200, 100.0, 150, 95.0),
    ]
    data = _build_dashboard_from_db_rows(rows, top_n=5, world_id="atm9")
    assert data["rows"] == 1
    note = data.get("note", {})
    assert note["dt_guard_count"] == 1
    assert note["min_dt_sec"] == 60
    item = data["top_amount_items"][0]
    assert item["growth_per_min"] == 0
    assert item["delta"] == 0
    assert item["dt_sec"] == pytest.approx(5.0)
    assert item["decrease_per_min"] == 0
