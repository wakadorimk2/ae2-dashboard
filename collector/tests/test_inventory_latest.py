from contextlib import contextmanager

from app.db import inventory_latest_rows, update_inventory_latest_prev
from app.models import IngestEntry


def test_inventory_latest_rows_uses_amount_then_count():
    entries = [
        IngestEntry(kind="item", raw_name="minecraft:stone", amount=5, count=9),
        IngestEntry(kind="fluid", raw_name="minecraft:water", count=3),
        IngestEntry(kind="gas", raw_name="mod:gas"),
    ]

    rows = inventory_latest_rows(entries, ts=123.4, world_id="atm9")

    assert rows == [
        ("atm9", "item", "minecraft:stone", 5, 123.4),
        ("atm9", "fluid", "minecraft:water", 3, 123.4),
        ("atm9", "gas", "mod:gas", 0, 123.4),
    ]


class FakeDatabaseState:
    def __init__(self, latest=None, prev=None):
        self.inventory_latest = dict(latest or {})
        self.inventory_prev = dict(prev or {})


class FakeCursor:
    def __init__(self, state: FakeDatabaseState):
        self.state = state
        self._rows: list[tuple] = []
        self.rowcount = 0

    def execute(self, query: str, params=None):
        normalized = query.strip().lower()
        if normalized.startswith("select"):
            params = params or []
            keys: list[tuple] = []
            it = iter(params)
            while True:
                try:
                    world_id = next(it)
                except StopIteration:
                    break
                kind = next(it)
                raw_name = next(it)
                keys.append((world_id, kind, raw_name))
            results = []
            for key in keys:
                if key in self.state.inventory_latest:
                    amount, ts = self.state.inventory_latest[key]
                    results.append((*key, amount, ts))
            self._rows = results
            self.rowcount = len(results)
        elif "inventory_prev" in normalized:
            params = params or []
            cols = 5
            entries = len(params) // cols
            for i in range(entries):
                offset = i * cols
                world_id, kind, raw_name, amount_prev, ts_prev = params[offset : offset + cols]
                key = (world_id, kind, raw_name)
                self.state.inventory_prev[key] = (amount_prev, float(ts_prev))
            self.rowcount = entries
        else:
            self.rowcount = 0

    def executemany(self, query: str, seq):
        for row in seq:
            world_id, kind, raw_name, amount, ts = row
            key = (world_id, kind, raw_name)
            self.state.inventory_latest[key] = (amount, float(ts))
        self.rowcount = len(seq)

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeConnection:
    def __init__(self, state: FakeDatabaseState):
        self.state = state

    def cursor(self):
        return FakeCursor(self.state)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def make_fake_db_connection(state: FakeDatabaseState):
    @contextmanager
    def _fake_db_connection():
        conn = FakeConnection(state)
        try:
            yield conn
        finally:
            pass

    return _fake_db_connection


def test_update_inventory_latest_prev_advances_prev(monkeypatch):
    state = FakeDatabaseState(
        latest={
            ("atm9", "item", "minecraft:stone"): (999, 1767859999.0),
        }
    )
    monkeypatch.setattr("app.db.db_connection", make_fake_db_connection(state))
    entry = IngestEntry(kind="item", raw_name="minecraft:stone", amount=1000)

    prev_rows, latest_rows = update_inventory_latest_prev([entry], ts=1767860000.0, world_id="atm9")

    assert prev_rows == 1
    assert latest_rows == 1
    assert state.inventory_latest[("atm9", "item", "minecraft:stone")] == (1000, 1767860000.0)
    assert state.inventory_prev[("atm9", "item", "minecraft:stone")] == (999, 1767859999.0)


def test_update_inventory_latest_prev_same_ts_leaves_prev_untouched(monkeypatch):
    state = FakeDatabaseState(
        latest={
            ("atm9", "item", "minecraft:stone"): (1000, 1767860000.0),
        },
        prev={
            ("atm9", "item", "minecraft:stone"): (995, 1767859000.0),
        },
    )
    monkeypatch.setattr("app.db.db_connection", make_fake_db_connection(state))
    entry = IngestEntry(kind="item", raw_name="minecraft:stone", amount=1001)

    prev_rows, latest_rows = update_inventory_latest_prev([entry], ts=1767860000.0, world_id="atm9")

    assert prev_rows == 0
    assert latest_rows == 1
    assert state.inventory_latest[("atm9", "item", "minecraft:stone")] == (1001, 1767860000.0)
    assert state.inventory_prev[("atm9", "item", "minecraft:stone")] == (995, 1767859000.0)


def test_update_inventory_latest_prev_ignores_older_ts(monkeypatch):
    state = FakeDatabaseState(
        latest={
            ("atm9", "item", "minecraft:stone"): (2000, 1767860001.0),
        }
    )
    monkeypatch.setattr("app.db.db_connection", make_fake_db_connection(state))
    entry = IngestEntry(kind="item", raw_name="minecraft:stone", amount=1990)

    prev_rows, latest_rows = update_inventory_latest_prev([entry], ts=1767860000.0, world_id="atm9")

    assert prev_rows == 0
    assert latest_rows == 0
    assert state.inventory_latest[("atm9", "item", "minecraft:stone")] == (2000, 1767860001.0)
    assert ("atm9", "item", "minecraft:stone") not in state.inventory_prev
