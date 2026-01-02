from __future__ import annotations
import json, time
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from . import settings
from .models import IngestPayload
from .storage_gcs import save_jsonl_to_gcs
from .summarize import summarize_items

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

    summary = summarize_items(payload.items)
    resp = {
        "ok": True,
        "gcs_path": gcs_path,
        "ts": payload.ts or time.time(),
        "source": payload.source,
        "items_len": len(payload.items),
        **summary,
    }

    print(json.dumps({"type": "ingest_summary", **resp}, ensure_ascii=False))
    return resp
