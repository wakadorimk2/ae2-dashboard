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

def compute_rankings(
    items: List[IngestItem],
    ts: float,
    top_n: int = 10,
    min_amount_for_top: int = 0,
) -> Dict[str, Any]:
    """
    1) top_amount: 絶対量 TopN（raw_name単位で合算）
    2) top_growth_per_min: 増加量 TopN（/min, 前回比, raw_name単位）
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

    # 増加 Top（/min）
    top_growth_fmt: List[Dict[str, Any]] = []
    if _prev_ts is not None:
        dt_min = max(ts - _prev_ts, 1.0) / 60.0

        # 前回も raw_name 単位に畳む
        prev_by_raw: Dict[str, int] = {}
        for (raw, _fp), amt in _prev_amounts.items():
            prev_by_raw[raw] = prev_by_raw.get(raw, 0) + amt

        growth = []
        for raw, amt in cur_by_raw.items():
            prev = prev_by_raw.get(raw, 0)
            delta = amt - prev
            if delta > 0:
                growth.append((raw, int(delta / dt_min)))

        growth.sort(key=lambda x: x[1], reverse=True)
        top_growth_fmt = [{"raw_name": raw, "growth_per_min": g} for raw, g in growth[:top_n]]

    # 状態更新
    _prev_amounts = cur
    _prev_ts = ts

    return {
        "top_amount": top_amount_fmt,
        "top_growth_per_min": top_growth_fmt,
    }