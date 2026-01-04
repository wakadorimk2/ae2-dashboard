from __future__ import annotations
import json, os, time
from typing import Any, Dict, Optional
from google.cloud import storage
from google.api_core.exceptions import NotFound
from . import settings

_storage_client = None

def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        project = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT")
            or os.getenv("PROJECT_ID")
        )
        _storage_client = storage.Client(project=project)
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

def save_json_to_gcs(payload_dict: Dict[str, Any], object_name: str) -> Optional[str]:
    if not settings.GCS_BUCKET:
        return None

    data = json.dumps(payload_dict, ensure_ascii=False)
    client = _get_storage_client()
    bucket = client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(object_name)
    blob.upload_from_string(data, content_type="application/json; charset=utf-8")
    return f"gs://{settings.GCS_BUCKET}/{object_name}"

def load_json_from_gcs(object_name: str) -> Optional[Dict[str, Any]]:
    if not settings.GCS_BUCKET:
        return None

    client = _get_storage_client()
    bucket = client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(object_name)
    try:
        text = blob.download_as_text()
    except NotFound:
        return None
    except Exception as exc:
        print(f"failed to load latest.json: {exc}")
        raise
    return json.loads(text)
