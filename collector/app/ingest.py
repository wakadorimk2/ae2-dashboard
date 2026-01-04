from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Tuple
from .models import IngestEntry, IngestItem, IngestPayload, normalize_kind

_KIND_PREFIX = {
    "fluid": "fluid:",
    "gas": "gas:",
}
_KIND_FROM_PREFIX = {
    "fluid:": "fluid",
    "gas:": "gas",
}

def _split_kind_prefix(raw_name: str) -> Tuple[Optional[str], str]:
    for prefix, kind in _KIND_FROM_PREFIX.items():
        if raw_name.startswith(prefix):
            return kind, raw_name[len(prefix) :]
    return None, raw_name

def _with_kind_prefix(kind: str, raw_name: str) -> str:
    kind = normalize_kind(kind)
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

def _normalize_entry(entry: IngestEntry) -> IngestEntry:
    kind = normalize_kind(entry.kind)
    prefix_kind, stripped = _split_kind_prefix(entry.raw_name)
    if prefix_kind:
        kind = prefix_kind
    if kind != entry.kind or stripped != entry.raw_name:
        return entry.model_copy(update={"kind": kind, "raw_name": stripped})
    return entry

def entries_to_items(entries: Iterable[IngestEntry]) -> Tuple[List[IngestItem], Dict[str, int]]:
    items: List[IngestItem] = []
    counts = {"item": 0, "fluid": 0, "gas": 0}
    for entry in entries:
        kind = normalize_kind(entry.kind)
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

def _legacy_kind_from_item(kind: str, item: IngestItem) -> Tuple[str, str]:
    prefix_kind, stripped = _split_kind_prefix(item.raw_name)
    if prefix_kind:
        return prefix_kind, stripped
    return normalize_kind(kind), item.raw_name

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

def _legacy_entry(kind: str, item: IngestItem) -> IngestEntry:
    resolved_kind, raw_name = _legacy_kind_from_item(kind, item)
    return IngestEntry(
        kind=resolved_kind,
        raw_name=raw_name,
        amount=item.amount,
        display_name=item.display_name,
        nbt_hash=item.nbt_hash,
        fingerprint=item.fingerprint,
        extra=item.extra,
    )

def legacy_to_entries(
    items: Optional[List[IngestItem]],
    fluids: Optional[List[IngestItem]],
    gases: Optional[List[IngestItem]],
) -> List[IngestEntry]:
    out: List[IngestEntry] = []
    if items:
        out.extend(_legacy_entry("item", it) for it in items)
    if fluids:
        out.extend(_legacy_entry("fluid", it) for it in fluids)
    if gases:
        out.extend(_legacy_entry("gas", it) for it in gases)
    return out

def normalize_to_entries(payload: IngestPayload) -> Tuple[List[IngestEntry], str]:
    if payload.entries:
        normalized = [_normalize_entry(entry) for entry in payload.entries]
        return normalized, "entries"

    if payload.items or payload.fluids or payload.gases:
        return legacy_to_entries(payload.items, payload.fluids, payload.gases), "legacy"

    if payload.entries is not None:
        return [], "entries"
    return [], "legacy"

def normalize_ingest_payload(
    payload: IngestPayload,
) -> Tuple[List[IngestItem], List[IngestEntry], Dict[str, int], str]:
    entries, schema = normalize_to_entries(payload)
    items, kind_counts = entries_to_items(entries)
    counts = {
        "items": kind_counts["item"],
        "fluids": kind_counts["fluid"],
        "gases": kind_counts["gas"],
        "entries": len(entries),
    }
    return items, entries, counts, schema
