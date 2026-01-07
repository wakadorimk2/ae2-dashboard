from __future__ import annotations

import sys
from pathlib import Path
import unittest

import yaml

COLLECTOR_ROOT = Path(__file__).resolve().parents[3]
if str(COLLECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLECTOR_ROOT))

from app.dag.aggregate_view import DEFAULT_GROUPS_PATH


class GroupsYamlContractTests(unittest.TestCase):
    def test_groups_yaml_contract(self) -> None:
        with DEFAULT_GROUPS_PATH.open("r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle) or {}

        if isinstance(doc, dict) and "groups" in doc:
            groups = doc["groups"]
        else:
            groups = doc

        self.assertIsInstance(groups, list)

        allowed_rule_keys = {"prefix", "contains_any", "contains_all", "kind_in"}
        seen_fingerprints = {}

        for index, group in enumerate(groups):
            self.assertIsInstance(group, dict)
            gid = group.get("id")
            self.assertTrue(gid, f"groups[{index}] is missing id")

            members = group.get("members")
            if members is None:
                continue
            self.assertIsInstance(members, dict)

            fingerprints = members.get("fingerprints")
            if fingerprints is not None:
                self.assertIsInstance(fingerprints, list)
                for fingerprint in fingerprints:
                    self.assertIsInstance(fingerprint, str)
                    if fingerprint in seen_fingerprints:
                        self.fail(
                            "duplicate fingerprint: "
                            f"{fingerprint} in {gid} and {seen_fingerprints[fingerprint]}"
                        )
                    seen_fingerprints[fingerprint] = gid

            rules = members.get("rules")
            if rules is not None:
                self.assertIsInstance(rules, list)
                for rule in rules:
                    self.assertIsInstance(rule, dict)
                    unknown_keys = set(rule) - allowed_rule_keys
                    self.assertFalse(unknown_keys, f"{gid} has unknown rule keys: {unknown_keys}")
