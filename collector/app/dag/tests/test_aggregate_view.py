from __future__ import annotations

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
