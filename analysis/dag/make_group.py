from __future__ import annotations

import json
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any, Optional

import yaml


def load_yaml(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def iter_jsonl(path: str | Path) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def norm_name(s: str) -> str:
    # まずは完全一致運用が最強。必要ならここに正規化を足す（lower/stripなど）
    return s.strip()


def rule_matches(rule: dict, fingerprint: str, kind: Optional[str]) -> bool:
    prefix = rule.get("prefix")
    if prefix and not fingerprint.startswith(prefix):
        return False

    contains_any = rule.get("contains_any")
    if contains_any and not any(token in fingerprint for token in contains_any):
        return False

    contains_all = rule.get("contains_all")
    if contains_all and not all(token in fingerprint for token in contains_all):
        return False

    kind_in = rule.get("kind_in")
    if kind_in and (kind is None or kind not in kind_in):
        return False

    return True


def _self_check() -> None:
    # Minimal sanity checks for the rules matcher.
    assert rule_matches({"prefix": "item:"}, "item:minecraft:iron_ore", None)
    assert not rule_matches({"prefix": "item:"}, "fluid:minecraft:water", None)

    assert rule_matches({"contains_all": ["iron", "_ore"]}, "item:minecraft:iron_ore", None)
    
    # contains_any の true/false を両方チェック
    assert rule_matches({"contains_any": ["_ore"]}, "item:minecraft:iron_ore", None)
    assert not rule_matches({"contains_any": ["_ore"]}, "item:minecraft:iron_ingot", None)


def resolve_group_id(
    fingerprint: str,
    kind: Optional[str],
    item_to_group: Dict[str, str],
    rules_chain: List[Tuple[str, dict]],
) -> Optional[str]:
    gid = item_to_group.get(fingerprint)
    if gid is not None:
        return gid

    # rules are fallback after explicit fingerprints
    for rule_gid, rule in rules_chain:
        if rule_matches(rule, fingerprint, kind):
            return rule_gid

    return None


def main(
    groups_yaml: str = "/mnt/data/groups.yaml",
    jsonl_path: str = "dashboard.jsonl",
    limit: int | None = None,
) -> None:
    _self_check()

    groups_doc = load_yaml(groups_yaml)

    # groups.yaml の形： { version: 1, groups: [...] }
    if isinstance(groups_doc, dict) and "groups" in groups_doc:
        groups = groups_doc["groups"]
    else:
        groups = groups_doc

    if not isinstance(groups, list):
        raise ValueError("groups.yaml must be a list (or dict with 'groups' list)")

    # item -> group_id
    item_to_group: Dict[str, str] = {}
    group_to_sector: Dict[str, str] = {}
    rules_chain: List[Tuple[str, dict]] = []

    for g in groups:
        gid = g["id"]

        # まだ sector が無いので、とりあえず kind を sector 代わりにしてもOK
        # （あとで groups.yaml に sector を足したらそのまま効く）
        group_to_sector[gid] = g.get("sector") or g.get("kind") or "misc"

        members = g.get("members") or {}
        fps = members.get("fingerprints") or []
        rules = members.get("rules") or []

        for fp in fps:
            item_to_group[norm_name(fp)] = gid
        for rule in rules:
            rules_chain.append((gid, rule))

    # 集計
    total_rows = 0
    unique_items = set()

    matched_rows = 0
    matched_unique = set()

    unknown_amount = Counter()
    unknown_delta = Counter()

    group_amount = defaultdict(float)
    group_delta = defaultdict(float)

    sector_amount = defaultdict(float)
    sector_delta = defaultdict(float)

    def get_amount(row: dict) -> int:
        # amount/qty/count どれでも拾えるように保険
        for k in ("amount", "qty", "count"):
            if k in row and isinstance(row[k], (int, float)):
                return int(row[k])
        return 0

    def get_delta(row: dict) -> int:
        # delta系も保険
        for k in ("delta_per_min", "growth_per_min", "delta"):
            if k in row and isinstance(row[k], (int, float)):
                return int(row[k])
        return 0
    
    for payload in iter_jsonl(jsonl_path):
        entries = payload.get("entries") or []

        by_fp = defaultdict(float)
        kind_by_fp: Dict[str, Optional[str]] = {}

        for e in entries:
            fp = e.get("fingerprint")
            if not fp:
                continue

            name = norm_name(fp)
            raw = float(e.get("amount") or 0)
            k = e.get("kind")  # "item" / "fluid" / "gas"

            # mB -> B (fluids/gases only)
            val = raw / 1000.0 if k in ("fluid", "gas") else raw

            by_fp[name] += val
            if name not in kind_by_fp:
                kind_by_fp[name] = k

        for name, amt in by_fp.items():
            total_rows += 1
            unique_items.add(name)

            dlt = 0.0

            gid = resolve_group_id(name, kind_by_fp.get(name), item_to_group, rules_chain)
            if gid is None:
                unknown_amount[name] += amt
                unknown_delta[name] += dlt
                continue

            matched_rows += 1
            matched_unique.add(name)

            group_amount[gid] += amt
            group_delta[gid] += dlt

            sid = group_to_sector.get(gid, "misc")
            sector_amount[sid] += amt
            sector_delta[sid] += dlt


    # レポート
    print("=== BASIC ===")
    print(f"rows: {total_rows}")
    print(f"unique items: {len(unique_items)}")
    print(f"matched rows: {matched_rows} ({matched_rows / max(total_rows,1):.1%})")
    print(f"matched unique items: {len(matched_unique)} ({len(matched_unique) / max(len(unique_items),1):.1%})")

    print("\n=== TOP UNKNOWN by amount ===")
    for name, v in unknown_amount.most_common(30):
        print(f"{v:>12.1f}  {name}")

    print("\n=== TOP UNKNOWN by delta ===")
    for name, v in unknown_delta.most_common(30):
        print(f"{v:>12.1f}  {name}")

    print("\n=== TOP GROUPS by amount ===")
    for gid, v in sorted(group_amount.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"{v:>12.1f}  {gid}")

    print("\n=== TOP SECTORS by amount ===")
    for sid, v in sorted(sector_amount.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"{v:>12.1f}  {sid}")

    print("\n(done)")


if __name__ == "__main__":
    # jsonl_path をあなたの実データに合わせて変えてね
    main(groups_yaml="/home/wakadori/repo/ae2-dashboard/collector/app/dag/defs/groups.yaml", jsonl_path="/mnt/c/Users/wakad/Downloads/1767543095-e530ae6d.jsonl", limit=None)
