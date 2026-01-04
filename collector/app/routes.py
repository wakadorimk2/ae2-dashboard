from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from . import limits, settings
from .ingest import normalize_ingest_payload
from .models import IngestEntry, IngestPayload
from .storage_gcs import save_jsonl_to_gcs, save_json_to_gcs, load_json_from_gcs
from .summarize import summarize_items, compute_rankings

router = APIRouter()
OPS_UI_DIR = Path(__file__).resolve().parent / "ops_ui"
OPS_UI_INDEX = OPS_UI_DIR / "index.html"

def _count_entry_kinds(entries: List[IngestEntry]) -> Dict[str, int]:
    counts = {"item": 0, "fluid": 0, "gas": 0}
    for entry in entries:
        kind = entry.kind
        if kind in counts:
            counts[kind] += 1
    return counts

def _latest_object_name() -> str:
    prefix = settings.GCS_PREFIX.strip("/")
    if prefix:
        return f"{prefix}/latest.json"
    return "latest.json"

def _select_rank_entries(entries: List[IngestEntry], max_entries: int) -> List[IngestEntry]:
    if len(entries) <= max_entries:
        return entries
    non_items = [entry for entry in entries if entry.kind in ("fluid", "gas")]
    items = [entry for entry in entries if entry.kind == "item"]
    if len(non_items) >= max_entries:
        return non_items[:max_entries]
    return non_items + items[: max_entries - len(non_items)]

@router.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "name": settings.APP_NAME, "ts": time.time()}

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "name": settings.APP_NAME, "ts": time.time()}

@router.post("/ingest")
def ingest(payload: IngestPayload) -> Dict[str, Any]:
    if payload.entries is None and payload.items is None and payload.fluids is None and payload.gases is None:
        raise HTTPException(status_code=400, detail="missing body.items or body.entries")

    raw_entries = payload.entries or []
    raw_entry_counts = None
    if payload.entries is not None:
        raw_entry_counts = _count_entry_kinds(raw_entries)
        print(
            "entries raw kind counts: item=%s fluid=%s gas=%s"
            % (
                raw_entry_counts.get("item", 0),
                raw_entry_counts.get("fluid", 0),
                raw_entry_counts.get("gas", 0),
            )
        )

    items, rank_entries, counts, schema = normalize_ingest_payload(payload)

    log = {
        "type": "ingest_received",
        "schema": schema,
        "counts": counts,
    }
    if payload.job_id is not None:
        log["job_id"] = payload.job_id
    if payload.seq is not None:
        log["seq"] = payload.seq
    if payload.total is not None:
        log["total"] = payload.total
    print(json.dumps(log, ensure_ascii=False))
    print(
        "counts: item=%s fluid=%s gas=%s"
        % (
            counts.get("items", 0),
            counts.get("fluids", 0),
            counts.get("gases", 0),
        )
    )

    if len(items) > settings.MAX_ITEMS:
        raise HTTPException(status_code=413, detail=f"too many items: {len(items)} > {settings.MAX_ITEMS}")

    if settings.LOG_RAW:
        # 元のmain.pyの挙動と同じ :contentReference[oaicite:2]{index=2}
        print(json.dumps({"type": "raw_payload", **payload.model_dump()}, ensure_ascii=False))

    normalized_payload = payload.model_copy(update={"entries": rank_entries})
    dump = normalized_payload.model_dump()
    gcs_path = save_jsonl_to_gcs(dump)

    ts = payload.ts or time.time()

    summary = summarize_items(items)
    rank_entry_counts = _count_entry_kinds(rank_entries)
    print(
        "entries rank kind counts: item=%s fluid=%s gas=%s"
        % (
            rank_entry_counts.get("item", 0),
            rank_entry_counts.get("fluid", 0),
            rank_entry_counts.get("gas", 0),
        )
    )
    if raw_entry_counts is not None:
        diff_counts = {
            "item": raw_entry_counts.get("item", 0) - rank_entry_counts.get("item", 0),
            "fluid": raw_entry_counts.get("fluid", 0) - rank_entry_counts.get("fluid", 0),
            "gas": raw_entry_counts.get("gas", 0) - rank_entry_counts.get("gas", 0),
        }
        print(
            "entries kind diff (raw - rank_all): item=%s fluid=%s gas=%s"
            % (
                diff_counts.get("item", 0),
                diff_counts.get("fluid", 0),
                diff_counts.get("gas", 0),
            )
        )
    if len(rank_entries) > limits.INGEST_MAX:
        rank_entries = _select_rank_entries(rank_entries, limits.INGEST_MAX)
    rank_entry_counts_used = _count_entry_kinds(rank_entries)
    ranks = compute_rankings(rank_entries, ts=ts, top_n=limits.RANKING_MAX, min_amount_for_top=0)
    print(
        "input kind counts: item=%s fluid=%s gas=%s output lens: top_amount_fluids=%s top_amount_gases=%s"
        % (
            rank_entry_counts_used.get("item", 0),
            rank_entry_counts_used.get("fluid", 0),
            rank_entry_counts_used.get("gas", 0),
            len(ranks.get("top_amount_fluids") or []),
            len(ranks.get("top_amount_gases") or []),
        )
    )
    resp = {
        "ok": True,
        "gcs_path": gcs_path,
        "ts": ts,
        "source": payload.source,
        "items_len": len(items),
        "top_n": limits.RANKING_MAX,
        **summary,
        **ranks,
    }

    if settings.GCS_BUCKET:
        try:
            save_json_to_gcs(resp, _latest_object_name())
        except Exception as exc:
            print(f"failed to save latest.json: {exc}")

    if resp.get("top_amount"):
        print("TOP_AMOUNT:")
        for r in resp["top_amount"][:5]:
            print(f"  {r['raw_name']} {r['amount']}")
    if resp.get("top_growth_per_min"):
        print("TOP_GROWTH(/min):")
        for r in resp["top_growth_per_min"][:5]:
            print(f"  {r['raw_name']} +{r['growth_per_min']}/min")

    print(json.dumps({"type": "ingest_summary", **resp}, ensure_ascii=False))
    return resp

@router.get("/dashboard")
def dashboard(top_n: int = Query(limits.API_MAX, ge=1)) -> Dict[str, Any]:
    if not settings.GCS_BUCKET:
        raise HTTPException(status_code=503, detail="GCS_BUCKET is not configured")

    object_name = _latest_object_name()
    try:
        data = load_json_from_gcs(object_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"failed to load latest dashboard from GCS: gs://{settings.GCS_BUCKET}/{object_name}: {exc}",
        )
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"latest dashboard not found: gs://{settings.GCS_BUCKET}/{object_name}",
        )

    top_n = min(top_n, limits.API_MAX)

    top = data.get("top")
    if isinstance(top, dict):
        for metric in top.values():
            if not isinstance(metric, dict):
                continue
            for kind, items in metric.items():
                if isinstance(items, list):
                    metric[kind] = items[:top_n]

    for key in (
        "top_amount_items","top_amount_fluids","top_amount_gases",
        "top_growth_per_min_items","top_growth_per_min_fluids","top_growth_per_min_gases",
        "top_decrease_per_min_items","top_decrease_per_min_fluids","top_decrease_per_min_gases",
    ):
        if isinstance(data.get(key), list):
            data[key] = data[key][:top_n]

    top = data.get("top")
    if not isinstance(top, dict):
        top = {}
        data["top"] = top

    def _merge_compat(metric_key: str, items_key: str, fluids_key: str, gases_key: str) -> None:
        metric = top.get(metric_key)
        if not isinstance(metric, dict):
            metric = {}
            top[metric_key] = metric
        items = data.get(items_key) if isinstance(data.get(items_key), list) else []
        fluids = data.get(fluids_key) if isinstance(data.get(fluids_key), list) else []
        gases = data.get(gases_key) if isinstance(data.get(gases_key), list) else []
        metric.setdefault("items", items)
        metric.setdefault("fluids", fluids)
        metric.setdefault("gases", gases)
        metric.setdefault("item", items)
        metric.setdefault("fluid", fluids)
        metric.setdefault("gas", gases)

    _merge_compat(
        "amount",
        "top_amount_items",
        "top_amount_fluids",
        "top_amount_gases",
    )
    _merge_compat(
        "growth_per_min",
        "top_growth_per_min_items",
        "top_growth_per_min_fluids",
        "top_growth_per_min_gases",
    )
    _merge_compat(
        "decrease_per_min",
        "top_decrease_per_min_items",
        "top_decrease_per_min_fluids",
        "top_decrease_per_min_gases",
    )

    data["top_n"] = top_n
    return data

@router.get("/dashboard/ui")
def dashboard_ui() -> FileResponse:
    if not OPS_UI_INDEX.exists():
        raise HTTPException(
            status_code=500,
            detail=f"dashboard UI not found: {OPS_UI_INDEX}",
        )
    return FileResponse(OPS_UI_INDEX)
