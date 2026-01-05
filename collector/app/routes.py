from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from . import limits, settings
from .ingest import normalize_ingest_payload
from .models import IngestEntry, IngestPayload
from .storage_gcs import save_jsonl_to_gcs, save_json_to_gcs, load_json_from_gcs
from .summarize import summarize_items, compute_rankings
from .dag.aggregate_view import aggregate_view

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

def _dashboard_view_object_name() -> str:
    prefix = settings.GCS_PREFIX.strip("/")
    base = "dashboard/view/latest.json"
    if prefix:
        return f"{prefix}/{base}"
    return base

def _entries_object_name(ts: float) -> str:
    prefix = settings.GCS_PREFIX.strip("/")
    ts_key = int(float(ts) * 1000)
    base = f"dashboard/snapshots/{ts_key}.json"
    if prefix:
        return f"{prefix}/{base}"
    return base

def _object_name_from_entries_path(entries_path: str) -> str:
    path = entries_path.strip()
    if path.startswith("gs://"):
        prefix = f"gs://{settings.GCS_BUCKET}/"
        if not path.startswith(prefix):
            raise ValueError("entries_path bucket mismatch")
        return path[len(prefix):]
    return path.lstrip("/")

def _dump_entries(entries: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict):
            out.append(entry)
        elif hasattr(entry, "model_dump"):
            out.append(entry.model_dump())
        elif hasattr(entry, "dict"):
            out.append(entry.dict())
    return out

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

    items, all_entries, rank_entries, counts, schema = normalize_ingest_payload(payload)
    ts = payload.ts or time.time()

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

    raw_entries_path = None
    if settings.GCS_BUCKET:
        entries_object_name = _entries_object_name(ts)
        print(f"raw entries object: gs://{settings.GCS_BUCKET}/{entries_object_name}")
        raw_payload = {"ts": ts, "entries": _dump_entries(all_entries)}
        try:
            raw_entries_path = save_json_to_gcs(raw_payload, entries_object_name)
        except Exception as exc:
            print(f"failed to save raw entries: {exc}")

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
    if raw_entries_path is not None:
        resp["entries_path"] = raw_entries_path

    if settings.GCS_BUCKET:
        try:
            print(f"latest object: gs://{settings.GCS_BUCKET}/{_latest_object_name()}")
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

@router.post("/jobs/aggregate")
def jobs_aggregate(top_n: int = Query(50, ge=1), ts: Optional[float] = Query(None)) -> Dict[str, Any]:
    if not settings.GCS_BUCKET:
        raise HTTPException(status_code=503, detail="GCS_BUCKET is not configured")

    latest_payload = None
    entries_object_name = None
    entries_source = None

    if ts is None:
        object_name = _latest_object_name()
        print(f"latest object: gs://{settings.GCS_BUCKET}/{object_name}")
        try:
            latest_payload = load_json_from_gcs(object_name)
        except Exception as exc:
            print(f"failed to load latest snapshot for aggregation: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"failed to load latest snapshot from GCS: gs://{settings.GCS_BUCKET}/{object_name}: {exc}",
            )
        if latest_payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"latest snapshot not found: gs://{settings.GCS_BUCKET}/{object_name}",
            )
        if not isinstance(latest_payload, dict):
            raise HTTPException(status_code=400, detail="latest snapshot is invalid")

        entries_source = (
            latest_payload.get("entries_path")
            or latest_payload.get("entries_object_name")
        )
        if not entries_source:
            raise HTTPException(status_code=400, detail="latest snapshot missing entries_path")
        try:
            entries_object_name = _object_name_from_entries_path(str(entries_source))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        entries_object_name = _entries_object_name(ts)
        entries_source = f"gs://{settings.GCS_BUCKET}/{entries_object_name}"

    print(f"raw entries object: gs://{settings.GCS_BUCKET}/{entries_object_name}")
    try:
        raw_payload = load_json_from_gcs(entries_object_name)
    except Exception as exc:
        print(f"failed to load raw entries for aggregation: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"failed to load raw entries from GCS: gs://{settings.GCS_BUCKET}/{entries_object_name}: {exc}",
        )
    if raw_payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"raw entries not found: {entries_source}",
        )
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="raw entries payload is invalid")

    entries = raw_payload.get("entries")
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail="raw entries missing entries")

    if latest_payload is not None:
        latest_ts = latest_payload.get("ts")
        raw_ts = raw_payload.get("ts")
        if latest_ts is not None and raw_ts is not None:
            try:
                diff = abs(float(latest_ts) - float(raw_ts))
            except (TypeError, ValueError):
                diff = None
            if diff is not None and diff > 1.0:
                print(f"warning: latest/raw ts mismatch: latest={latest_ts} raw={raw_ts}")

    try:
        view_ts = None
        if latest_payload is not None:
            view_ts = latest_payload.get("ts")
        if view_ts is None:
            view_ts = raw_payload.get("ts") or ts
        view = aggregate_view(entries, top_n=top_n, ts=view_ts)
    except Exception as exc:
        print(f"failed to aggregate view: {exc}")
        raise HTTPException(status_code=500, detail=f"failed to aggregate view: {exc}")

    view_object_name = _dashboard_view_object_name()
    try:
        print(f"view object: gs://{settings.GCS_BUCKET}/{view_object_name}")
        gcs_path = save_json_to_gcs(view, view_object_name)
    except Exception as exc:
        print(f"failed to save dashboard view: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"failed to save dashboard view to GCS: gs://{settings.GCS_BUCKET}/{view_object_name}: {exc}",
        )

    if gcs_path is None:
        gcs_path = f"gs://{settings.GCS_BUCKET}/{view_object_name}"

    return {"ok": True, "ts": view.get("ts"), "view_path": gcs_path}

@router.get("/dashboard/view")
def dashboard_view() -> Dict[str, Any]:
    if not settings.GCS_BUCKET:
        raise HTTPException(status_code=503, detail="GCS_BUCKET is not configured")

    object_name = _dashboard_view_object_name()
    try:
        data = load_json_from_gcs(object_name)
    except Exception as exc:
        print(f"failed to load dashboard view from GCS: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"failed to load dashboard view from GCS: gs://{settings.GCS_BUCKET}/{object_name}: {exc}",
        )
    if data is None:
        raise HTTPException(status_code=404, detail="Not Found")

    return data

@router.get("/dashboard/ui")
def dashboard_ui() -> FileResponse:
    if not OPS_UI_INDEX.exists():
        raise HTTPException(
            status_code=500,
            detail=f"dashboard UI not found: {OPS_UI_INDEX}",
        )
    return FileResponse(OPS_UI_INDEX, headers={"Cache-Control": "no-store"})
