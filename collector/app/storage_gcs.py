from __future__ import annotations
import json, os, time
from typing import Any, Dict, Optional
from google.cloud import storage
from . import settings

_storage_client = None

def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client

def save_jsonl_to_gcs(payload_dict: Dict[str, Any]) -> Optional[str]:
    if not settings.GCS_BUCKET:
        return None

    ts = payload_dict.get("ts") or time.time()
    ts_int = int(float(ts))
    day = time.strftime("%Y/%m/%d", time.gmtime(ts_int))
    fname = f"{ts_int}-{os.urandom(4).hex()}.jsonl"
    object_name = f"{settings.GCS_PREFIX}/{day}/{fname}"

    line = json.dumps(payload_dict, ensure_ascii=False) + "\n"

    client = _get_storage_client()
    bucket = client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(object_name)
    blob.upload_from_string(line, content_type="application/jsonl; charset=utf-8")
    return f"gs://{settings.GCS_BUCKET}/{object_name}"
