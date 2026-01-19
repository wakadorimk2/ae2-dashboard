from __future__ import annotations

import sys
from pathlib import Path
import unittest

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
if str(COLLECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLECTOR_ROOT))

from app.dag.graph import (
    DEFAULT_EDGES_PATH,
    DEFAULT_GROUPS_PATH,
    build_graph,
    immediate_upstream,
    topo_order,
    validate_graph,
)
from app.dag.stats import build_stats_from_snapshots


class DagGraphTests(unittest.TestCase):
    def test_defs_graph_is_dag(self) -> None:
        graph = build_graph(DEFAULT_GROUPS_PATH, DEFAULT_EDGES_PATH)
        validate_graph(graph)
        order = topo_order(graph)
        self.assertTrue(order)

    def test_immediate_upstream_from_defs(self) -> None:
        graph = build_graph(DEFAULT_GROUPS_PATH, DEFAULT_EDGES_PATH)
        upstream = immediate_upstream(graph, "brine")
        upstream_ids = {item["group_id"] for item in upstream}
        self.assertIn("evaporation", upstream_ids)
        evaporation = next((item for item in upstream if item["group_id"] == "evaporation"), None)
        self.assertIsNotNone(evaporation)
        self.assertIn("confidence", evaporation)


class DagStatsTests(unittest.TestCase):
    def test_missing_fingerprint_keeps_previous(self) -> None:
        groups_doc = {
            "groups": [
                {
                    "id": "water_out",
                    "members": {"fingerprints": ["fluid:water"]},
                }
            ]
        }
        snapshots = [
            (0.0, {"fluid:water": 10.0}),
            (60.0, {}),
        ]
        stats = build_stats_from_snapshots(groups_doc, snapshots, short_minutes=10.0, mid_minutes=60.0)
        self.assertIn("water_out", stats)
        self.assertEqual(stats["water_out"].amount, 10.0)
