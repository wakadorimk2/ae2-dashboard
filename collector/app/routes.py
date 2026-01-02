from __future__ import annotations
import json, time
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from . import settings
from .models import IngestPayload
from .storage_gcs import save_jsonl_to_gcs
from .summarize import summarize_items, compute_rankings

router = APIRouter()

@router.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "name": settings.APP_NAME, "ts": time.time()}

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "name": settings.APP_NAME, "ts": time.time()}

@router.post("/ingest")
def ingest(payload: IngestPayload) -> Dict[str, Any]:
    if len(payload.items) > settings.MAX_ITEMS:
        raise HTTPException(status_code=413, detail=f"too many items: {len(payload.items)} > {settings.MAX_ITEMS}")

    if settings.LOG_RAW:
        # 元のmain.pyの挙動と同じ :contentReference[oaicite:2]{index=2}
        print(json.dumps({"type": "raw_payload", **payload.model_dump()}, ensure_ascii=False))

    dump = payload.model_dump()
    gcs_path = save_jsonl_to_gcs(dump)

    ts = payload.ts or time.time()

    summary = summarize_items(payload.items)
    ranks = compute_rankings(payload.items, ts=ts, top_n=10, min_amount_for_top=0)
    resp = {
        "ok": True,
        "gcs_path": gcs_path,
        "ts": payload.ts or time.time(),
        "source": payload.source,
        "items_len": len(payload.items),
        **summary,
        **ranks,
    }

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
