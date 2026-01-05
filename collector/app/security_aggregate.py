from __future__ import annotations

import hmac
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_BODY_BYTES = 1024 * 1024
TIMESTAMP_SKEW_SEC = 180
NONCE_TTL_SEC = 300
RATE_LIMIT_SEC = 60
MAX_NONCE_LEN = 128

_nonce_cache: Dict[str, float] = {}
_rate_limit: Dict[str, float] = {}
_lock = threading.Lock()


class AggregatePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    network_id: str = Field(..., min_length=1, max_length=64)
    job_id: Optional[str] = None
    entries: Optional[List[Dict[str, Any]]] = None
    payload: Optional[Dict[str, Any]] = None


def _prune_nonce(now: float) -> None:
    expired_keys = [key for key, expiry in _nonce_cache.items() if expiry <= now]
    for key in expired_keys:
        del _nonce_cache[key]


def _prune_rate_limit(now: float) -> None:
    expired_keys = [key for key, seen in _rate_limit.items() if now - seen > RATE_LIMIT_SEC]
    for key in expired_keys:
        del _rate_limit[key]


async def aggregate_guard(request: Request) -> AggregatePayload:
    expected_key = os.getenv("AGGREGATE_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="AGGREGATE_API_KEY is not configured")

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="missing X-API-Key")
    if not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(status_code=401, detail="invalid X-API-Key")

    timestamp_header = request.headers.get("X-Timestamp")
    if not timestamp_header:
        raise HTTPException(status_code=401, detail="missing X-Timestamp")
    try:
        request_ts = float(timestamp_header)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="invalid X-Timestamp (expected unix seconds)")
    now = time.time()
    if abs(now - request_ts) > TIMESTAMP_SKEW_SEC:
        raise HTTPException(status_code=401, detail="X-Timestamp out of range")

    nonce = request.headers.get("X-Nonce")
    if not nonce:
        raise HTTPException(status_code=401, detail="missing X-Nonce")
    if len(nonce) > MAX_NONCE_LEN:
        raise HTTPException(status_code=401, detail="X-Nonce too long")

    nonce_key = f"{timestamp_header}:{nonce}"
    with _lock:
        _prune_nonce(now)
        if nonce_key in _nonce_cache:
            raise HTTPException(status_code=401, detail="replayed X-Nonce")
        _nonce_cache[nonce_key] = now + NONCE_TTL_SEC

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    if not body:
        raise HTTPException(status_code=400, detail="missing body")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid body: expected JSON object")

    try:
        payload = AggregatePayload.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"invalid body: {exc.errors()}")

    network_id = payload.network_id
    now = time.time()
    with _lock:
        _prune_rate_limit(now)
        last_seen = _rate_limit.get(network_id)
        if last_seen is not None and now - last_seen < RATE_LIMIT_SEC:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        _rate_limit[network_id] = now

    request.state.aggregate_payload = payload
    return payload
