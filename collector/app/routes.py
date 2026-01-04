from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from . import limits, settings
from .ingest import normalize_ingest_payload
from .models import IngestPayload
from .storage_gcs import save_jsonl_to_gcs, save_json_to_gcs, load_json_from_gcs
from .summarize import summarize_items, compute_rankings

router = APIRouter()
OPS_UI_DIR = Path(__file__).resolve().parent / "ops_ui"
OPS_UI_INDEX = OPS_UI_DIR / "index.html"

def _latest_object_name() -> str:
    prefix = settings.GCS_PREFIX.strip("/")
    if prefix:
        return f"{prefix}/latest.json"
    return "latest.json"

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

    items, counts, schema = normalize_ingest_payload(payload)

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

    dump = payload.model_dump()
    gcs_path = save_jsonl_to_gcs(dump)

    ts = payload.ts or time.time()

    summary = summarize_items(items)
    rank_items = items
    if len(rank_items) > limits.INGEST_MAX:
        rank_items = rank_items[:limits.INGEST_MAX]
    ranks = compute_rankings(rank_items, ts=ts, top_n=limits.RANKING_MAX, min_amount_for_top=0)
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
