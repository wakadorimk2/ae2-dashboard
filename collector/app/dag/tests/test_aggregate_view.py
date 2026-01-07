from __future__ import annotations

import math
import sys
from pathlib import Path
import unittest

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
if str(COLLECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLECTOR_ROOT))

from app.dag.aggregate_view import aggregate_view, rule_matches


class AggregateViewTests(unittest.TestCase):
    def test_rule_matches(self) -> None:
        self.assertTrue(rule_matches({"prefix": "item:"}, "item:foo", None))
        self.assertFalse(rule_matches({"prefix": "item:"}, "fluid:foo", None))

        self.assertTrue(rule_matches({"contains_any": ["foo", "bar"]}, "item:foo", None))
        self.assertFalse(rule_matches({"contains_any": ["foo"]}, "item:baz", None))

        self.assertTrue(rule_matches({"contains_all": ["foo", "bar"]}, "item:foo_bar", None))
        self.assertFalse(rule_matches({"contains_all": ["foo", "bar"]}, "item:foo", None))

        self.assertTrue(rule_matches({"kind_in": ["item", "fluid"]}, "item:foo", "item"))
        self.assertFalse(rule_matches({"kind_in": ["fluid"]}, "item:foo", "item"))

    def test_amount_normalization(self) -> None:
        entries = [
            {"fingerprint": "fluid:test:water", "kind": "fluid", "amount": 1500},
            {"fingerprint": "gas:test:steam", "kind": "gas", "amount": 2000},
            {"fingerprint": "item:test:iron", "kind": "item", "amount": 3},
        ]
        view = aggregate_view(entries, top_n=10, ts=0)
        items = view["top_items_by_sector"].get("misc", [])
        by_fp = {item["fingerprint"]: item for item in items}

        self.assertAlmostEqual(by_fp["fluid:test:water"]["amount"], 1.5)
        self.assertAlmostEqual(by_fp["gas:test:steam"]["amount"], 2.0)
        self.assertAlmostEqual(by_fp["item:test:iron"]["amount"], 3.0)

    def test_aggregate_view_invariants(self) -> None:
        entries = [
            {"fingerprint": "fluid:minecraft:water", "kind": "fluid", "amount": 1000, "delta_per_min": 50},
            {"fingerprint": "item:minecraft:cobblestone", "kind": "item", "amount": 120},
            {"fingerprint": "item:gtceu:sulfur_dust", "kind": "item", "amount": 8},
            {"fingerprint": "item:minecraft:iron_ingot", "kind": "item", "amount": 4},
            {"fingerprint": "item:some_mod:totally_unknown_thing", "kind": "item", "amount": 1},
        ]
        view = aggregate_view(entries, top_n=50, ts=0)

        sectors = view["sectors"]
        groups = view["groups"]
        sector_ids = {sector["id"] for sector in sectors}
        group_ids = {group["id"] for group in groups}
        group_sector = {group["id"]: group["sector"] for group in groups}

        for group in groups:
            self.assertIn(group["sector"], sector_ids)
            self.assertGreaterEqual(group["amount"], 0.0)
            self.assertTrue(math.isfinite(group["amount"]))
            self.assertTrue(math.isfinite(group["delta_per_min"]))

        for sector in sectors:
            self.assertGreaterEqual(sector["amount"], 0.0)
            self.assertTrue(math.isfinite(sector["amount"]))
            self.assertTrue(math.isfinite(sector["delta_per_min"]))

        for sector_id in view["top_items_by_sector"]:
            self.assertIn(sector_id, sector_ids)

        for sector_id, items in view["top_items_by_sector"].items():
            for item in items:
                self.assertIn(item["group"], group_ids)
                self.assertEqual(group_sector[item["group"]], sector_id)
                self.assertGreaterEqual(item["amount"], 0.0)
                self.assertTrue(math.isfinite(item["amount"]))

    def test_grouping_golden(self) -> None:
        entries = [
            {"fingerprint": "fluid:minecraft:water", "kind": "fluid", "amount": 1000},
            {"fingerprint": "fluid:minecraft:lava", "kind": "fluid", "amount": 1000},
            {"fingerprint": "item:minecraft:cobblestone", "kind": "item", "amount": 32},
            {"fingerprint": "item:alltheores:nether_osmium_ore", "kind": "item", "amount": 2},
            {"fingerprint": "item:gtceu:sulfur_dust", "kind": "item", "amount": 2},
            {"fingerprint": "item:minecraft:iron_ingot", "kind": "item", "amount": 2},
            {"fingerprint": "item:some_mod:totally_unknown_thing", "kind": "item", "amount": 1},
        ]
        view = aggregate_view(entries, top_n=50, ts=0)

        by_fp = {}
        for items in view["top_items_by_sector"].values():
            for item in items:
                by_fp[item["fingerprint"]] = item

        self.assertEqual(by_fp["fluid:minecraft:water"]["group"], "water_source")
        self.assertEqual(by_fp["fluid:minecraft:lava"]["group"], "lava_source")
        self.assertEqual(by_fp["item:minecraft:cobblestone"]["group"], "cobble_source")
        self.assertEqual(by_fp["item:alltheores:nether_osmium_ore"]["group"], "ore_input")
        self.assertEqual(by_fp["item:gtceu:sulfur_dust"]["group"], "ore_preprocess")
        self.assertEqual(by_fp["item:minecraft:iron_ingot"]["group"], "ore_products")

        unknown_items = [
            item
            for item in view["top_items_by_sector"].get("misc", [])
            if item["fingerprint"] == "item:some_mod:totally_unknown_thing"
        ]
        self.assertTrue(unknown_items)
        self.assertEqual(unknown_items[0]["group"], "unknown")
