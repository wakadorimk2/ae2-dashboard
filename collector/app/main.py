from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from google.cloud import storage

APP_NAME = os.getenv("APP_NAME", "ae2-collector")
LOG_RAW = os.getenv("LOG_RAW", "0") == "1"          # 1にすると受信payloadを丸ごとログ（重いので注意）
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "200000"))  # 想定より多いときの保険
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_PREFIX = os.getenv("GCS_PREFIX", "raw")  # 保存先のprefix


app = FastAPI(title=APP_NAME)


class IngestItem(BaseModel):
    raw_name: str = Field(..., description="例: minecraft:stone / ae2:certus_quartz_crystal")
    amount: int = Field(..., ge=0)
    display_name: Optional[str] = None
    nbt_hash: Optional[str] = None
    fingerprint: Optional[str] = Field(
        None,
        description="variants識別用。raw_name + nbt_hash などをCC側で作れればベスト"
    )
    # CC側の都合で他フィールドが来ても落ちないように
    extra: Dict[str, Any] = Field(default_factory=dict)


class IngestPayload(BaseModel):
    ts: Optional[float] = Field(None, description="UNIX秒 or ISOでもOK（UNIX推奨）")
    source: Optional[str] = Field(None, description="拠点名/次元/ワールド名など任意")
    items: List[IngestItem]

@app.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "name": APP_NAME, "ts": time.time()}

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "name": APP_NAME, "ts": time.time()}


def _normalize_key(item: IngestItem) -> str:
    # いまのセッション方針：まず raw_name を正規化キーにする
    return item.raw_name.strip().lower()


def _variant_key(item: IngestItem) -> str:
    # fingerprint があればそれを優先。なければ raw_name 単体（＝variantsは増えないが安全）
    if item.fingerprint and item.fingerprint.strip():
        return item.fingerprint
    if item.nbt_hash and item.nbt_hash.strip():
        return f"{item.raw_name}#{item.nbt_hash}"
    return item.raw_name


_storage_client = None

def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client

def save_jsonl_to_gcs(payload_dict: Dict[str, Any]) -> Optional[str]:
    if not GCS_BUCKET:
        return None

    # 1リクエスト=1行jsonl（後でまとめたくなったらDataflow/BigQueryで）
    ts = payload_dict.get("ts") or time.time()
    # tsがfloatでも安全に
    ts_int = int(float(ts))
    day = time.strftime("%Y/%m/%d", time.gmtime(ts_int))
    fname = f"{ts_int}-{os.urandom(4).hex()}.jsonl"
    object_name = f"{GCS_PREFIX}/{day}/{fname}"

    line = json.dumps(payload_dict, ensure_ascii=False) + "\n"

    client = _get_storage_client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(object_name)
    blob.upload_from_string(line, content_type="application/jsonl; charset=utf-8")
    return f"gs://{GCS_BUCKET}/{object_name}"


@app.post("/ingest")
def ingest(payload: IngestPayload) -> Dict[str, Any]:
    if len(payload.items) > MAX_ITEMS:
        raise HTTPException(status_code=413, detail=f"too many items: {len(payload.items)} > {MAX_ITEMS}")

    if LOG_RAW:
        # payloadがデカいとログ費用も増えるのでデバッグ時だけ
        app.logger.info("RAW_PAYLOAD %s", json.dumps(payload.model_dump(), ensure_ascii=False))
    
    # GCSに保存
    dump = payload.model_dump()
    gcs_path = save_jsonl_to_gcs(dump)

    # 集計
    by_norm: Dict[str, Dict[str, Any]] = {}
    variant_sets: Dict[str, set] = {}

    total_amount = 0
    for it in payload.items:
        norm = _normalize_key(it)
        total_amount += it.amount

        if norm not in by_norm:
            by_norm[norm] = {"amount": 0, "display_name": it.display_name or None}
            variant_sets[norm] = set()

        by_norm[norm]["amount"] += it.amount

        # display_name は最初に取れたやつを温存（後で改善してもOK）
        if (not by_norm[norm]["display_name"]) and it.display_name:
            by_norm[norm]["display_name"] = it.display_name

        variant_sets[norm].add(_variant_key(it))

    kinds = len(by_norm)
    variants_total = sum(len(s) for s in variant_sets.values())
    variants_max = max((len(s) for s in variant_sets.values()), default=0)

    # variantsが多い上位（NBT爆発の匂い）を少しだけ返す
    top_variants = sorted(
        ((k, len(v)) for k, v in variant_sets.items()),
        key=lambda x: x[1],
        reverse=True
    )[:20]

    # ログ（Cloud Loggingで見やすいよう JSON で出す）
    summary = {
        "ts": payload.ts or time.time(),
        "source": payload.source,
        "items_len": len(payload.items),
        "kinds_normalized": kinds,
        "variants_total": variants_total,
        "variants_max_per_kind": variants_max,
        "total_amount": total_amount,
        "top_variants": top_variants,
    }
    print(json.dumps({"type": "ingest_summary", **summary}, ensure_ascii=False))

    return {"ok": True, "gcs_path": gcs_path, **summary}
