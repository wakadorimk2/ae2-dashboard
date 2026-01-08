from app.db import inventory_latest_rows
from app.models import IngestEntry


def test_inventory_latest_rows_uses_amount_then_count():
    entries = [
        IngestEntry(kind="item", raw_name="minecraft:stone", amount=5, count=9),
        IngestEntry(kind="fluid", raw_name="minecraft:water", count=3),
        IngestEntry(kind="gas", raw_name="mod:gas"),
    ]

    rows = inventory_latest_rows(entries, ts=123.4)

    assert rows == [
        ("item", "minecraft:stone", 5, 123.4),
        ("fluid", "minecraft:water", 3, 123.4),
        ("gas", "mod:gas", 0, 123.4),
    ]
