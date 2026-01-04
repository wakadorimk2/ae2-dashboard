from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import time
from .models import IngestItem, IngestEntry
from . import limits

def normalize_key(item: IngestItem) -> str:
    return item.raw_name.strip().lower()

def variant_key(item: IngestItem) -> str:
    if item.fingerprint and item.fingerprint.strip():
        return item.fingerprint
    if item.nbt_hash and item.nbt_hash.strip():
        return f"{item.raw_name}#{item.nbt_hash}"
    return item.raw_name

def summarize_items(items: List[IngestItem]) -> Dict[str, Any]:
    by_norm: Dict[str, Dict[str, Any]] = {}
    variant_sets: Dict[str, set] = {}
    total_amount = 0

    for it in items:
        norm = normalize_key(it)
        total_amount += it.amount

        if norm not in by_norm:
            by_norm[norm] = {"amount": 0, "display_name": it.display_name or None}
            variant_sets[norm] = set()

        by_norm[norm]["amount"] += it.amount

        if (not by_norm[norm]["display_name"]) and it.display_name:
            by_norm[norm]["display_name"] = it.display_name

        variant_sets[norm].add(variant_key(it))

    kinds = len(by_norm)
    variants_total = sum(len(s) for s in variant_sets.values())
    variants_max = max((len(s) for s in variant_sets.values()), default=0)

    top_variants: List[Tuple[str, int]] = sorted(
        ((k, len(v)) for k, v in variant_sets.items()),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    return {
        "kinds_normalized": kinds,
        "variants_total": variants_total,
        "variants_max_per_kind": variants_max,
        "total_amount": total_amount,
        "top_variants": top_variants,
    }

# --- ランキング用の「前回状態」(メモリ保持) ---
_prev_amounts: Dict[str, int] = {}
_prev_meta: Dict[str, Dict[str, str]] = {}
_prev_ts: Optional[float] = None

def _entry_amount(entry: IngestEntry) -> int:
    if entry.amount is not None:
        return entry.amount
    if entry.count is not None:
        return entry.count
    return 0

def _strip_kind_prefix(kind: str, raw_name: str) -> str:
    if kind == "fluid" and raw_name.startswith("fluid:"):
        return raw_name[len("fluid:") :]
    if kind == "gas" and raw_name.startswith("gas:"):
        return raw_name[len("gas:") :]
    return raw_name

def _rank_key(kind: str, raw_name: str, fingerprint: Optional[str]) -> str:
    if fingerprint and fingerprint.strip():
        return fingerprint.strip()
    return f"{kind}:{raw_name}"

def compute_rankings(
    entries: List[IngestEntry],
    ts: float,
    top_n: int = limits.RANKING_MAX,
    min_amount_for_top: int = 0,
) -> Dict[str, Any]:
    """
    1) top_amount: 絶対量 TopN（fingerprint優先、なければkind:raw_nameで集計）
    2) top_growth_per_min: 増加量 TopN（/min, 前回比, 同キー単位）
    3) top_decrease_per_min: 減少量 TopN（/min, 前回比, 正の値で返す）
    ※ Cloud Runの再起動で前回状態はリセットされる（最初の1回はgrowth空）
    """
    global _prev_amounts, _prev_meta, _prev_ts

    # 今回スナップショット（fingerprint優先で集計キーを作る）
    cur: Dict[str, int] = {}
    cur_meta: Dict[str, Dict[str, str]] = {}
    for entry in entries:
        kind = entry.kind
        raw_name = _strip_kind_prefix(kind, entry.raw_name)
        key = _rank_key(kind, raw_name, entry.fingerprint)
        cur[key] = cur.get(key, 0) + _entry_amount(entry)

        meta = cur_meta.get(key)
        if meta is None:
            cur_meta[key] = {
                "raw_name": raw_name,
                "display_name": entry.display_name or raw_name,
                "kind": kind,
            }
        else:
            if (not meta.get("display_name")) and entry.display_name:
                meta["display_name"] = entry.display_name
            if (not meta.get("raw_name")) and raw_name:
                meta["raw_name"] = raw_name

    # 絶対量 Top
    top_amount = sorted(
        ((key, amt) for key, amt in cur.items() if amt >= min_amount_for_top),
        key=lambda x: x[1],
        reverse=True,
    )[:top_n]
    top_amount_fmt = [
        {"raw_name": cur_meta.get(key, {}).get("raw_name") or key, "amount": amt}
        for key, amt in top_amount
    ]

    top_amount_items: List[Tuple[str, int]] = []
    top_amount_fluids: List[Tuple[str, int]] = []
    top_amount_gases: List[Tuple[str, int]] = []
    for key, amt in cur.items():
        if amt < min_amount_for_top:
            continue
        kind = cur_meta.get(key, {}).get("kind", "item")
        if kind == "fluid":
            top_amount_fluids.append((key, amt))
        elif kind == "gas":
            top_amount_gases.append((key, amt))
        else:
            top_amount_items.append((key, amt))

    top_amount_items.sort(key=lambda x: x[1], reverse=True)
    top_amount_fluids.sort(key=lambda x: x[1], reverse=True)
    top_amount_gases.sort(key=lambda x: x[1], reverse=True)

    top_amount_items_fmt = [
        {
            "raw_name": cur_meta.get(key, {}).get("raw_name") or key,
            "amount": amt,
            "kind": "item",
            "display_name": cur_meta.get(key, {}).get("display_name")
            or cur_meta.get(key, {}).get("raw_name")
            or key,
        }
        for key, amt in top_amount_items[:top_n]
    ]
    top_amount_fluids_fmt = [
        {
            "raw_name": cur_meta.get(key, {}).get("raw_name") or key,
            "amount": amt,
            "kind": "fluid",
            "display_name": cur_meta.get(key, {}).get("display_name")
            or cur_meta.get(key, {}).get("raw_name")
            or key,
        }
        for key, amt in top_amount_fluids[:top_n]
    ]
    top_amount_gases_fmt = [
        {
            "raw_name": cur_meta.get(key, {}).get("raw_name") or key,
            "amount": amt,
            "kind": "gas",
            "display_name": cur_meta.get(key, {}).get("display_name")
            or cur_meta.get(key, {}).get("raw_name")
            or key,
        }
        for key, amt in top_amount_gases[:top_n]
    ]

    # 増加 Top（/min）
    top_growth_fmt: List[Dict[str, Any]] = []
    top_decrease_fmt: List[Dict[str, Any]] = []
    top_growth_items_fmt: List[Dict[str, Any]] = []
    top_growth_fluids_fmt: List[Dict[str, Any]] = []
    top_growth_gases_fmt: List[Dict[str, Any]] = []
    top_decrease_items_fmt: List[Dict[str, Any]] = []
    top_decrease_fluids_fmt: List[Dict[str, Any]] = []
    top_decrease_gases_fmt: List[Dict[str, Any]] = []
    if _prev_ts is not None:
        dt_min = max(ts - _prev_ts, 1.0) / 60.0

        growth: List[Tuple[str, int]] = []
        decrease: List[Tuple[str, int]] = []
        all_keys = set(cur.keys()) | set(_prev_amounts.keys())
        for key in all_keys:
            amt = cur.get(key, 0)
            prev = _prev_amounts.get(key, 0)
            delta = amt - prev
            if delta > 0:
                growth.append((key, int(delta / dt_min)))
            elif delta < 0:
                decrease.append((key, int((-delta) / dt_min)))

        growth.sort(key=lambda x: x[1], reverse=True)
        top_growth_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "growth_per_min": g,
            }
            for key, g in growth[:top_n]
        ]
        decrease.sort(key=lambda x: x[1], reverse=True)
        top_decrease_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "decrease_per_min": g,
            }
            for key, g in decrease[:top_n]
        ]

        growth_items: List[Tuple[str, int]] = []
        growth_fluids: List[Tuple[str, int]] = []
        growth_gases: List[Tuple[str, int]] = []
        for key, g in growth:
            kind = (cur_meta.get(key) or _prev_meta.get(key) or {}).get("kind", "item")
            if kind == "fluid":
                growth_fluids.append((key, g))
            elif kind == "gas":
                growth_gases.append((key, g))
            else:
                growth_items.append((key, g))

        decrease_items: List[Tuple[str, int]] = []
        decrease_fluids: List[Tuple[str, int]] = []
        decrease_gases: List[Tuple[str, int]] = []
        for key, g in decrease:
            kind = (cur_meta.get(key) or _prev_meta.get(key) or {}).get("kind", "item")
            if kind == "fluid":
                decrease_fluids.append((key, g))
            elif kind == "gas":
                decrease_gases.append((key, g))
            else:
                decrease_items.append((key, g))

        growth_items.sort(key=lambda x: x[1], reverse=True)
        growth_fluids.sort(key=lambda x: x[1], reverse=True)
        growth_gases.sort(key=lambda x: x[1], reverse=True)
        decrease_items.sort(key=lambda x: x[1], reverse=True)
        decrease_fluids.sort(key=lambda x: x[1], reverse=True)
        decrease_gases.sort(key=lambda x: x[1], reverse=True)

        top_growth_items_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "growth_per_min": g,
                "kind": "item",
                "display_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("display_name")
                or (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name")
                or key,
            }
            for key, g in growth_items[:top_n]
        ]
        top_growth_fluids_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "growth_per_min": g,
                "kind": "fluid",
                "display_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("display_name")
                or (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name")
                or key,
            }
            for key, g in growth_fluids[:top_n]
        ]
        top_growth_gases_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "growth_per_min": g,
                "kind": "gas",
                "display_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("display_name")
                or (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name")
                or key,
            }
            for key, g in growth_gases[:top_n]
        ]
        top_decrease_items_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "decrease_per_min": g,
                "kind": "item",
                "display_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("display_name")
                or (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name")
                or key,
            }
            for key, g in decrease_items[:top_n]
        ]
        top_decrease_fluids_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "decrease_per_min": g,
                "kind": "fluid",
                "display_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("display_name")
                or (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name")
                or key,
            }
            for key, g in decrease_fluids[:top_n]
        ]
        top_decrease_gases_fmt = [
            {
                "raw_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name") or key,
                "decrease_per_min": g,
                "kind": "gas",
                "display_name": (cur_meta.get(key) or _prev_meta.get(key) or {}).get("display_name")
                or (cur_meta.get(key) or _prev_meta.get(key) or {}).get("raw_name")
                or key,
            }
            for key, g in decrease_gases[:top_n]
        ]

    # 状態更新
    _prev_amounts = cur
    _prev_meta = cur_meta
    _prev_ts = ts

    return {
        "top_amount": top_amount_fmt,
        "top_growth_per_min": top_growth_fmt,
        "top_decrease_per_min": top_decrease_fmt,
        "top": {
            "amount": {
                "item": top_amount_items_fmt,
                "fluid": top_amount_fluids_fmt,
                "gas": top_amount_gases_fmt,
            },
            "growth_per_min": {
                "item": top_growth_items_fmt,
                "fluid": top_growth_fluids_fmt,
                "gas": top_growth_gases_fmt,
            },
            "decrease_per_min": {
                "item": top_decrease_items_fmt,
                "fluid": top_decrease_fluids_fmt,
                "gas": top_decrease_gases_fmt,
            },
        },
        "top_amount_items": top_amount_items_fmt,
        "top_amount_fluids": top_amount_fluids_fmt,
        "top_amount_gases": top_amount_gases_fmt,
        "top_growth_per_min_items": top_growth_items_fmt,
        "top_growth_per_min_fluids": top_growth_fluids_fmt,
        "top_growth_per_min_gases": top_growth_gases_fmt,
        "top_decrease_per_min_items": top_decrease_items_fmt,
        "top_decrease_per_min_fluids": top_decrease_fluids_fmt,
        "top_decrease_per_min_gases": top_decrease_gases_fmt,
    }
