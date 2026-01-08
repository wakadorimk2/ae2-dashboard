from app.models import IngestEntry
from app.routes import _select_rank_entries
from app.summarize import compute_rankings


def test_rank_entries_selects_top_amount_item():
    entries = [
        IngestEntry(kind="item", raw_name=f"minecraft:item_{i}", amount=i + 1)
        for i in range(500)
    ]
    entries.append(
        IngestEntry(kind="item", raw_name="minecraft:raw_gold_block", amount=10000)
    )

    selected = _select_rank_entries(entries, 500)
    ranks = compute_rankings(selected, ts=1.0, top_n=500, min_amount_for_top=0)
    raw_names = {row.get("raw_name") for row in ranks.get("top_amount_items", [])}

    assert "minecraft:raw_gold_block" in raw_names


def test_rank_entries_selects_top_count_item():
    entries = [
        IngestEntry(kind="item", raw_name=f"minecraft:item_{i}", count=i + 1)
        for i in range(5)
    ]
    entries.append(
        IngestEntry(kind="item", raw_name="minecraft:raw_gold_block", count=9999)
    )

    selected = _select_rank_entries(entries, 3)
    ranks = compute_rankings(selected, ts=1.0, top_n=3, min_amount_for_top=0)
    raw_names = {row.get("raw_name") for row in ranks.get("top_amount_items", [])}

    assert "minecraft:raw_gold_block" in raw_names
