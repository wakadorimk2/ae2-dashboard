from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

DEFAULT_GROUPS_PATH = Path(__file__).resolve().parent / "defs" / "groups.yaml"

_GROUPS_CACHE: Optional[Tuple[Dict[str, str], Dict[str, str], List[Tuple[str, dict]]]] = None


def load_yaml(path: Path | str) -> dict:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def norm_name(name: str) -> str:
    return name.strip()


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


def load_groups_cached() -> Tuple[Dict[str, str], Dict[str, str], List[Tuple[str, dict]]]:
    global _GROUPS_CACHE
    if _GROUPS_CACHE is not None:
        return _GROUPS_CACHE

    groups_doc = load_yaml(DEFAULT_GROUPS_PATH)
    if isinstance(groups_doc, dict) and "groups" in groups_doc:
        groups = groups_doc["groups"]
    else:
        groups = groups_doc

    if not isinstance(groups, list):
        raise ValueError("groups.yaml must be a list (or dict with 'groups' list)")

    item_to_group: Dict[str, str] = {}
    group_to_sector: Dict[str, str] = {}
    rules_chain: List[Tuple[str, dict]] = []

    for group in groups:
        gid = group.get("id")
        if not gid:
            continue

        group_to_sector[gid] = group.get("sector") or group.get("kind") or "misc"

        members = group.get("members") or {}
        fps = members.get("fingerprints") or []
        rules = members.get("rules") or []

        for fp in fps:
            item_to_group[norm_name(fp)] = gid
        for rule in rules:
            rules_chain.append((gid, rule))

    _GROUPS_CACHE = (item_to_group, group_to_sector, rules_chain)
    return _GROUPS_CACHE


def resolve_group_id(
    fingerprint: str,
    kind: Optional[str],
    item_to_group: Dict[str, str],
    rules_chain: List[Tuple[str, dict]],
) -> Optional[str]:
    gid = item_to_group.get(fingerprint)
    if gid is not None:
        return gid

    for rule_gid, rule in rules_chain:
        if rule_matches(rule, fingerprint, kind):
            return rule_gid

    return None


def _entry_amount(entry: dict) -> float:
    for key in ("amount", "qty", "count"):
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _entry_delta(entry: dict) -> float:
    for key in ("delta_per_min", "growth_per_min", "delta"):
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def aggregate_view(entries: List[dict], top_n: int, ts: Optional[float] = None) -> dict:
    item_to_group, group_to_sector, rules_chain = load_groups_cached()

    top_n = max(1, int(top_n))
    if ts is None:
        ts_value = time.time()
    else:
        try:
            ts_value = float(ts)
        except (TypeError, ValueError):
            ts_value = time.time()

    amount_by_fp: Dict[str, float] = defaultdict(float)
    delta_by_fp: Dict[str, float] = defaultdict(float)
    kind_by_fp: Dict[str, Optional[str]] = {}

    for entry in entries or []:
        if not isinstance(entry, dict):
            if hasattr(entry, "model_dump"):
                entry = entry.model_dump()
            elif hasattr(entry, "dict"):
                entry = entry.dict()
            else:
                continue

        fingerprint = entry.get("fingerprint")
        if not fingerprint:
            kind = entry.get("kind")
            raw_name = entry.get("raw_name")
            if kind and raw_name:
                fingerprint = f"{kind}:{raw_name}"
            else:
                continue
        fingerprint = norm_name(fingerprint)

        kind = entry.get("kind")
        amount = _entry_amount(entry)
        delta = _entry_delta(entry)

        if kind in ("fluid", "gas"):
            amount /= 1000.0
            delta /= 1000.0

        amount_by_fp[fingerprint] += amount
        delta_by_fp[fingerprint] += delta
        if fingerprint not in kind_by_fp:
            kind_by_fp[fingerprint] = kind

    sector_amount: Dict[str, float] = defaultdict(float)
    sector_delta: Dict[str, float] = defaultdict(float)
    group_amount: Dict[str, float] = defaultdict(float)
    group_delta: Dict[str, float] = defaultdict(float)
    top_items_by_sector: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for fingerprint, amount in amount_by_fp.items():
        kind = kind_by_fp.get(fingerprint)
        delta = delta_by_fp.get(fingerprint, 0.0)

        gid = resolve_group_id(fingerprint, kind, item_to_group, rules_chain)
        if gid is None:
            gid = "unknown"
        sector_id = group_to_sector.get(gid, "misc") if gid != "unknown" else "misc"

        group_amount[gid] += amount
        group_delta[gid] += delta
        sector_amount[sector_id] += amount
        sector_delta[sector_id] += delta

        top_items_by_sector[sector_id].append(
            {
                "fingerprint": fingerprint,
                "kind": kind,
                "amount": float(amount),
                "group": gid,
            }
        )

    sectors = [
        {
            "id": sector_id,
            "amount": float(amount),
            "delta_per_min": float(sector_delta.get(sector_id, 0.0)),
        }
        for sector_id, amount in sector_amount.items()
    ]
    sectors.sort(key=lambda row: (-row["amount"], row["id"]))

    groups = [
        {
            "id": group_id,
            "sector": group_to_sector.get(group_id, "misc") if group_id != "unknown" else "misc",
            "amount": float(amount),
            "delta_per_min": float(group_delta.get(group_id, 0.0)),
        }
        for group_id, amount in group_amount.items()
    ]
    groups.sort(key=lambda row: (-row["amount"], row["id"]))

    for sector_id, items in top_items_by_sector.items():
        items.sort(key=lambda row: row["amount"], reverse=True)
        top_items_by_sector[sector_id] = items[:top_n]

    return {
        "ts": ts_value,
        "sectors": sectors,
        "groups": groups,
        "top_items_by_sector": top_items_by_sector,
    }
