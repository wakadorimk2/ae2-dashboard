import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import _compute_growth_per_min

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

    assert isinstance(data.get("top_amount"), list)
    top = data.get("top")
    assert isinstance(top, dict)
    for metric in ("amount", "growth_per_min", "decrease_per_min"):
        assert isinstance(top.get(metric), dict)
        for kind in ("item", "fluid", "gas"):
            assert isinstance(top[metric].get(kind), list)
