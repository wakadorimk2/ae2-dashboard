from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Tuple
from .models import IngestEntry, IngestItem, IngestPayload

_KIND_PREFIX = {
    "fluid": "fluid:",
    "gas": "gas:",
}

def _with_kind_prefix(kind: str, raw_name: str) -> str:
    prefix = _KIND_PREFIX.get(kind)
    if not prefix:
        return raw_name
    if raw_name.startswith(prefix):
        return raw_name
    return f"{prefix}{raw_name}"

def _coerce_amount(entry: IngestEntry) -> int:
    if entry.amount is not None:
        return entry.amount
    if entry.count is not None:
        return entry.count
    return 0

def entries_to_items(entries: Iterable[IngestEntry]) -> Tuple[List[IngestItem], Dict[str, int]]:
    items: List[IngestItem] = []
    counts = {"item": 0, "fluid": 0, "gas": 0}
    for entry in entries:
        kind = entry.kind
        raw_name = _with_kind_prefix(kind, entry.raw_name)
        items.append(IngestItem(
            raw_name=raw_name,
            amount=_coerce_amount(entry),
            display_name=entry.display_name,
            nbt_hash=entry.nbt_hash,
            fingerprint=entry.fingerprint,
            extra=entry.extra,
        ))
        if kind in counts:
            counts[kind] += 1
    return items, counts

def _legacy_with_prefix(kind: str, item: IngestItem) -> IngestItem:
    raw_name = _with_kind_prefix(kind, item.raw_name)
    if raw_name == item.raw_name:
        return item
    return item.model_copy(update={"raw_name": raw_name})

def legacy_to_items(
    items: Optional[List[IngestItem]],
    fluids: Optional[List[IngestItem]],
    gases: Optional[List[IngestItem]],
) -> List[IngestItem]:
    out: List[IngestItem] = []
    if items:
        out.extend(items)
    if fluids:
        out.extend(_legacy_with_prefix("fluid", it) for it in fluids)
    if gases:
        out.extend(_legacy_with_prefix("gas", it) for it in gases)
    return out

def _should_use_entries(payload: IngestPayload) -> bool:
    if payload.entries is None:
        return False
    if payload.entries:
        return True
    if payload.items or payload.fluids or payload.gases:
        return False
    return True

def normalize_ingest_payload(payload: IngestPayload) -> Tuple[List[IngestItem], Dict[str, int], str]:
    use_entries = _should_use_entries(payload)

    if use_entries:
        items, kind_counts = entries_to_items(payload.entries or [])
        counts = {
            "items": kind_counts["item"],
            "fluids": kind_counts["fluid"],
            "gases": kind_counts["gas"],
            "entries": len(payload.entries or []),
        }
        return items, counts, "entries"

    items = legacy_to_items(payload.items, payload.fluids, payload.gases)
    counts = {
        "items": len(payload.items or []),
        "fluids": len(payload.fluids or []),
        "gases": len(payload.gases or []),
        "entries": len(payload.entries or []),
    }
    return items, counts, "legacy"
