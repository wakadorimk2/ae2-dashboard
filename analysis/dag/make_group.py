from __future__ import annotations

import json
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any

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


def main(
    groups_yaml: str = "/mnt/data/groups.yaml",
    jsonl_path: str = "dashboard.jsonl",
    limit: int | None = None,
) -> None:
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

    for g in groups:
        gid = g["id"]

        # まだ sector が無いので、とりあえず kind を sector 代わりにしてもOK
        # （あとで groups.yaml に sector を足したらそのまま効く）
        group_to_sector[gid] = g.get("sector") or g.get("kind") or "misc"

        members = g.get("members") or {}
        fps = members.get("fingerprints") or []

        for fp in fps:
            item_to_group[norm_name(fp)] = gid

    # 集計
    total_rows = 0
    unique_items = set()

    matched_rows = 0
    matched_unique = set()

    unknown_amount = Counter()
    unknown_delta = Counter()

    group_amount = defaultdict(int)
    group_delta = defaultdict(int)

    sector_amount = defaultdict(int)
    sector_delta = defaultdict(int)

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

        by_fp = defaultdict(int)
        for e in entries:
            fp = e.get("fingerprint")
            if fp:
                by_fp[norm_name(fp)] += int(e.get("amount") or 0)

        for name, amt in by_fp.items():
            total_rows += 1
            unique_items.add(name)

            dlt = 0  # このスナップショット形式だと delta は無いので 0 でOK

            gid = item_to_group.get(name)
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
        print(f"{v:>12}  {name}")

    print("\n=== TOP UNKNOWN by delta ===")
    for name, v in unknown_delta.most_common(30):
        print(f"{v:>12}  {name}")

    print("\n=== TOP GROUPS by amount ===")
    for gid, v in sorted(group_amount.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"{v:>12}  {gid}")

    print("\n=== TOP SECTORS by amount ===")
    for sid, v in sorted(sector_amount.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"{v:>12}  {sid}")

    print("\n(done)")


if __name__ == "__main__":
    # jsonl_path をあなたの実データに合わせて変えてね
    main(groups_yaml="/home/wakadori/repo/ae2-dashboard/collector/app/dag/defs/groups.yaml", jsonl_path="/mnt/c/Users/wakad/Downloads/1767543095-e530ae6d.jsonl", limit=None)
