from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import time
from .models import IngestItem

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
_prev_amounts: Dict[Tuple[str, str], int] = {}
_prev_ts: Optional[float] = None

def _key_raw_fp(it: IngestItem) -> Tuple[str, str]:
    return (it.raw_name, it.fingerprint or "")

def _kind_and_name(raw: str) -> Tuple[str, str]:
    if raw.startswith("fluid:"):
        return "fluid", raw[len("fluid:") :]
    if raw.startswith("gas:"):
        return "gas", raw[len("gas:") :]
    return "item", raw

def compute_rankings(
    items: List[IngestItem],
    ts: float,
    top_n: int = 10,
    min_amount_for_top: int = 0,
) -> Dict[str, Any]:
    """
    1) top_amount: 絶対量 TopN（raw_name単位で合算）
    2) top_growth_per_min: 増加量 TopN（/min, 前回比, raw_name単位）
    3) top_decrease_per_min: 減少量 TopN（/min, 前回比, raw_name単位, 正の値で返す）
    ※ Cloud Runの再起動で前回状態はリセットされる（最初の1回はgrowth空）
    """
    global _prev_amounts, _prev_ts

    # 今回スナップショット（raw_name + fingerprint 単位）
    cur: Dict[Tuple[str, str], int] = {}
    for it in items:
        k = _key_raw_fp(it)
        cur[k] = cur.get(k, 0) + it.amount

    # raw_name単位に畳む（fingerprint違いは合算）
    cur_by_raw: Dict[str, int] = {}
    for (raw, _fp), amt in cur.items():
        cur_by_raw[raw] = cur_by_raw.get(raw, 0) + amt

    # 絶対量 Top
    top_amount = sorted(
        ((raw, amt) for raw, amt in cur_by_raw.items() if amt >= min_amount_for_top),
        key=lambda x: x[1],
        reverse=True,
    )[:top_n]
    top_amount_fmt = [{"raw_name": raw, "amount": amt} for raw, amt in top_amount]

    top_amount_items: List[Tuple[str, int]] = []
    top_amount_fluids: List[Tuple[str, int]] = []
    top_amount_gases: List[Tuple[str, int]] = []
    for raw, amt in cur_by_raw.items():
        if amt < min_amount_for_top:
            continue
        kind, _name = _kind_and_name(raw)
        if kind == "fluid":
            top_amount_fluids.append((raw, amt))
        elif kind == "gas":
            top_amount_gases.append((raw, amt))
        else:
            top_amount_items.append((raw, amt))

    top_amount_items.sort(key=lambda x: x[1], reverse=True)
    top_amount_fluids.sort(key=lambda x: x[1], reverse=True)
    top_amount_gases.sort(key=lambda x: x[1], reverse=True)

    top_amount_items_fmt = [
        {"raw_name": raw, "amount": amt, "kind": "item", "display_name": _kind_and_name(raw)[1]}
        for raw, amt in top_amount_items[:top_n]
    ]
    top_amount_fluids_fmt = [
        {"raw_name": raw, "amount": amt, "kind": "fluid", "display_name": _kind_and_name(raw)[1]}
        for raw, amt in top_amount_fluids[:top_n]
    ]
    top_amount_gases_fmt = [
        {"raw_name": raw, "amount": amt, "kind": "gas", "display_name": _kind_and_name(raw)[1]}
        for raw, amt in top_amount_gases[:top_n]
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

        # 前回も raw_name 単位に畳む
        prev_by_raw: Dict[str, int] = {}
        for (raw, _fp), amt in _prev_amounts.items():
            prev_by_raw[raw] = prev_by_raw.get(raw, 0) + amt

        growth: List[Tuple[str, int]] = []
        decrease: List[Tuple[str, int]] = []
        all_raws = set(cur_by_raw.keys()) | set(prev_by_raw.keys())
        for raw in all_raws:
            amt = cur_by_raw.get(raw, 0)
            prev = prev_by_raw.get(raw, 0)
            delta = amt - prev
            if delta > 0:
                growth.append((raw, int(delta / dt_min)))
            elif delta < 0:
                decrease.append((raw, int((-delta) / dt_min)))

        growth.sort(key=lambda x: x[1], reverse=True)
        top_growth_fmt = [{"raw_name": raw, "growth_per_min": g} for raw, g in growth[:top_n]]
        decrease.sort(key=lambda x: x[1], reverse=True)
        top_decrease_fmt = [{"raw_name": raw, "decrease_per_min": g} for raw, g in decrease[:top_n]]

        growth_items: List[Tuple[str, int]] = []
        growth_fluids: List[Tuple[str, int]] = []
        growth_gases: List[Tuple[str, int]] = []
        for raw, g in growth:
            kind, _name = _kind_and_name(raw)
            if kind == "fluid":
                growth_fluids.append((raw, g))
            elif kind == "gas":
                growth_gases.append((raw, g))
            else:
                growth_items.append((raw, g))

        decrease_items: List[Tuple[str, int]] = []
        decrease_fluids: List[Tuple[str, int]] = []
        decrease_gases: List[Tuple[str, int]] = []
        for raw, g in decrease:
            kind, _name = _kind_and_name(raw)
            if kind == "fluid":
                decrease_fluids.append((raw, g))
            elif kind == "gas":
                decrease_gases.append((raw, g))
            else:
                decrease_items.append((raw, g))

        growth_items.sort(key=lambda x: x[1], reverse=True)
        growth_fluids.sort(key=lambda x: x[1], reverse=True)
        growth_gases.sort(key=lambda x: x[1], reverse=True)
        decrease_items.sort(key=lambda x: x[1], reverse=True)
        decrease_fluids.sort(key=lambda x: x[1], reverse=True)
        decrease_gases.sort(key=lambda x: x[1], reverse=True)

        top_growth_items_fmt = [
            {"raw_name": raw, "growth_per_min": g, "kind": "item", "display_name": _kind_and_name(raw)[1]}
            for raw, g in growth_items[:top_n]
        ]
        top_growth_fluids_fmt = [
            {"raw_name": raw, "growth_per_min": g, "kind": "fluid", "display_name": _kind_and_name(raw)[1]}
            for raw, g in growth_fluids[:top_n]
        ]
        top_growth_gases_fmt = [
            {"raw_name": raw, "growth_per_min": g, "kind": "gas", "display_name": _kind_and_name(raw)[1]}
            for raw, g in growth_gases[:top_n]
        ]
        top_decrease_items_fmt = [
            {"raw_name": raw, "decrease_per_min": g, "kind": "item", "display_name": _kind_and_name(raw)[1]}
            for raw, g in decrease_items[:top_n]
        ]
        top_decrease_fluids_fmt = [
            {"raw_name": raw, "decrease_per_min": g, "kind": "fluid", "display_name": _kind_and_name(raw)[1]}
            for raw, g in decrease_fluids[:top_n]
        ]
        top_decrease_gases_fmt = [
            {"raw_name": raw, "decrease_per_min": g, "kind": "gas", "display_name": _kind_and_name(raw)[1]}
            for raw, g in decrease_gases[:top_n]
        ]

    # 状態更新
    _prev_amounts = cur
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
