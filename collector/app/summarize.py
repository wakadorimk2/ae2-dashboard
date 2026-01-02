from __future__ import annotations
from typing import Any, Dict, List, Tuple
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
