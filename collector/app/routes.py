from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from . import limits, settings
from .ingest import normalize_ingest_payload
from .models import IngestEntry, IngestPayload
from .db import load_inventory_latest_with_prev, update_inventory_latest_prev
from .storage_gcs import save_jsonl_to_gcs, save_json_to_gcs, load_json_from_gcs
from .summarize import summarize_items, compute_rankings, _entry_amount
from .dag.aggregate_view import aggregate_view
from .security_aggregate import AggregatePayload, aggregate_guard

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
    base = "latest.json"
    if prefix:
        return f"{prefix}/{base}"
    return base

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
    return sorted(entries, key=_entry_amount, reverse=True)[:max_entries]

def _compute_growth_info(
    latest_amount: int,
    latest_ts: float,
    prev_amount: Optional[int],
    prev_ts: Optional[float],
) -> tuple[float, int, float, bool]:
    """Return (growth_per_min, delta, dt_sec, guard_applied)."""
    if prev_amount is None or prev_ts is None:
        return 0.0, 0, 0.0, False
    dt_raw = latest_ts - prev_ts
    if dt_raw <= 0:
        return 0.0, 0, 0.0, False
    dt_sec = float(dt_raw)
    guard_applied = dt_sec < settings.MIN_DT_SEC
    if guard_applied:
        return 0.0, 0, dt_sec, True
    delta = latest_amount - prev_amount
    growth_per_min = delta / dt_sec * 60.0
    return growth_per_min, delta, dt_sec, False


def _compute_growth_per_min(
    latest_amount: int,
    latest_ts: float,
    prev_amount: Optional[int],
    prev_ts: Optional[float],
) -> float:
    growth, _, _, _ = _compute_growth_info(latest_amount, latest_ts, prev_amount, prev_ts)
    return growth
def _build_dashboard_from_db_rows(
    rows: List[tuple],
    top_n: int,
    world_id: str,
) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    latest_ts = None
    dt_guard_count = 0
    for kind, raw_name, amount, ts, prev_amount, prev_ts in rows:
        try:
            amount_value = int(amount)
        except (TypeError, ValueError):
            continue
        try:
            ts_value = float(ts)
        except (TypeError, ValueError):
            continue
        prev_amount_value = None
        if prev_amount is not None:
            try:
                prev_amount_value = int(prev_amount)
            except (TypeError, ValueError):
                prev_amount_value = None
        prev_ts_value = None
        if prev_ts is not None:
            try:
                prev_ts_value = float(prev_ts)
            except (TypeError, ValueError):
                prev_ts_value = None
        growth_per_min, delta_value, dt_sec_value, guard_applied = _compute_growth_info(
            amount_value,
            ts_value,
            prev_amount_value,
            prev_ts_value,
        )
        if guard_applied:
            dt_guard_count += 1
        decrease_per_min = abs(growth_per_min) if growth_per_min < 0 else 0.0
        entries.append(
            {
                "kind": kind,
                "raw_name": raw_name,
                "display_name": raw_name,
                "amount": amount_value,
                "growth_per_min": growth_per_min,
                "decrease_per_min": decrease_per_min,
                "delta": delta_value,
                "dt_sec": dt_sec_value,
            }
        )
        if latest_ts is None or ts_value > latest_ts:
            latest_ts = ts_value

    def _format_amount(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "raw_name": entry["raw_name"],
            "amount": entry["amount"],
            "kind": entry["kind"],
            "display_name": entry["display_name"],
            "growth_per_min": entry["growth_per_min"],
            "decrease_per_min": entry["decrease_per_min"],
            "delta": entry["delta"],
            "dt_sec": entry["dt_sec"],
        }

    def _format_growth(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "raw_name": entry["raw_name"],
            "growth_per_min": entry["growth_per_min"],
            "kind": entry["kind"],
            "display_name": entry["display_name"],
        }

    def _format_decrease(entry: Dict[str, Any], decrease_value: float) -> Dict[str, Any]:
        return {
            "raw_name": entry["raw_name"],
            "decrease_per_min": decrease_value,
            "kind": entry["kind"],
            "display_name": entry["display_name"],
        }

    amount_sorted = sorted(entries, key=lambda e: e["amount"], reverse=True)
    top_amount = [{"raw_name": e["raw_name"], "amount": e["amount"]} for e in amount_sorted[:top_n]]

    growth_entries = [e for e in entries if e["growth_per_min"] > 0]
    growth_sorted = sorted(growth_entries, key=lambda e: e["growth_per_min"], reverse=True)
    top_growth = [
        {"raw_name": e["raw_name"], "growth_per_min": e["growth_per_min"]}
        for e in growth_sorted[:top_n]
    ]

    decrease_entries = [e for e in entries if e["growth_per_min"] < 0]
    decrease_sorted = sorted(decrease_entries, key=lambda e: abs(e["growth_per_min"]), reverse=True)
    top_decrease = [
        {"raw_name": e["raw_name"], "decrease_per_min": abs(e["growth_per_min"])}
        for e in decrease_sorted[:top_n]
    ]

    by_kind = {"item": [], "fluid": [], "gas": []}
    for entry in entries:
        kind = entry["kind"]
        if kind in by_kind:
            by_kind[kind].append(entry)

    top_amount_items = [_format_amount(e) for e in sorted(by_kind["item"], key=lambda e: e["amount"], reverse=True)[:top_n]]
    top_amount_fluids = [_format_amount(e) for e in sorted(by_kind["fluid"], key=lambda e: e["amount"], reverse=True)[:top_n]]
    top_amount_gases = [_format_amount(e) for e in sorted(by_kind["gas"], key=lambda e: e["amount"], reverse=True)[:top_n]]

    top_growth_items = [_format_growth(e) for e in sorted([e for e in by_kind["item"] if e["growth_per_min"] > 0], key=lambda e: e["growth_per_min"], reverse=True)[:top_n]]
    top_growth_fluids = [_format_growth(e) for e in sorted([e for e in by_kind["fluid"] if e["growth_per_min"] > 0], key=lambda e: e["growth_per_min"], reverse=True)[:top_n]]
    top_growth_gases = [_format_growth(e) for e in sorted([e for e in by_kind["gas"] if e["growth_per_min"] > 0], key=lambda e: e["growth_per_min"], reverse=True)[:top_n]]

    top_decrease_items = [
        _format_decrease(e, abs(e["growth_per_min"]))
        for e in sorted([e for e in by_kind["item"] if e["growth_per_min"] < 0], key=lambda e: abs(e["growth_per_min"]), reverse=True)[:top_n]
    ]
    top_decrease_fluids = [
        _format_decrease(e, abs(e["growth_per_min"]))
        for e in sorted([e for e in by_kind["fluid"] if e["growth_per_min"] < 0], key=lambda e: abs(e["growth_per_min"]), reverse=True)[:top_n]
    ]
    top_decrease_gases = [
        _format_decrease(e, abs(e["growth_per_min"]))
        for e in sorted([e for e in by_kind["gas"] if e["growth_per_min"] < 0], key=lambda e: abs(e["growth_per_min"]), reverse=True)[:top_n]
    ]

    data: Dict[str, Any] = {
        "ts": latest_ts,
        "source": "db",
        "world_id": world_id,
        "top_amount": top_amount,
        "top_growth_per_min": top_growth,
        "top_decrease_per_min": top_decrease,
        "top": {
            "amount": {
                "item": top_amount_items,
                "fluid": top_amount_fluids,
                "gas": top_amount_gases,
            },
            "growth_per_min": {
                "item": top_growth_items,
                "fluid": top_growth_fluids,
                "gas": top_growth_gases,
            },
            "decrease_per_min": {
                "item": top_decrease_items,
                "fluid": top_decrease_fluids,
                "gas": top_decrease_gases,
            },
        },
        "top_amount_items": top_amount_items,
        "top_amount_fluids": top_amount_fluids,
        "top_amount_gases": top_amount_gases,
        "top_growth_per_min_items": top_growth_items,
        "top_growth_per_min_fluids": top_growth_fluids,
        "top_growth_per_min_gases": top_growth_gases,
        "top_decrease_per_min_items": top_decrease_items,
        "top_decrease_per_min_fluids": top_decrease_fluids,
        "top_decrease_per_min_gases": top_decrease_gases,
    }
    data["rows"] = len(entries)
    data["note"] = {
        "dt_guard_count": dt_guard_count,
        "min_dt_sec": settings.MIN_DT_SEC,
    }
    if dt_guard_count:
        print(
            json.dumps(
                {
                    "type": "dashboard_dt_guard",
                    "world_id": world_id,
                    "count": dt_guard_count,
                    "min_dt_sec": settings.MIN_DT_SEC,
                    "ts": time.time(),
                },
                ensure_ascii=False,
            )
        )
    return data

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

    world_id = payload.world_id or settings.DEFAULT_WORLD_ID
    try:
        prev_rows, latest_rows = update_inventory_latest_prev(all_entries, ts, world_id)
        print(
            json.dumps(
                {
                    "type": "db_update_latest_prev",
                    "ok": True,
                    "prev_rows": prev_rows,
                    "latest_rows": latest_rows,
                    "ts": ts,
                    "world_id": world_id,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "type": "db_update_latest_prev",
                    "ok": False,
                    "error": str(exc),
                    "ts": ts,
                    "world_id": world_id,
                },
                ensure_ascii=False,
            )
        )
        # DBは追加の保存先として扱い、失敗しても既存フローを継続する。
        print(f"failed to update inventory_latest/inventory_prev: {exc}")

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
        try:
            view_object_name = _dashboard_view_object_name()
            existing_view = None
            try:
                existing_view = load_json_from_gcs(view_object_name)
            except Exception as exc:
                print(f"failed to load current dashboard view: {exc}")
            should_update_view = True
            if isinstance(existing_view, dict):
                existing_ts = existing_view.get("ts")
                try:
                    existing_ts = float(existing_ts) if existing_ts is not None else None
                except (TypeError, ValueError):
                    existing_ts = None
                try:
                    incoming_ts = float(ts)
                except (TypeError, ValueError):
                    incoming_ts = None
                if existing_ts is not None and incoming_ts is not None and incoming_ts <= existing_ts:
                    should_update_view = False
            if should_update_view:
                view = aggregate_view(_dump_entries(all_entries), top_n=limits.RANKING_MAX, ts=ts)
                if isinstance(gcs_path, str):
                    view["gcs_path"] = gcs_path
                if isinstance(raw_entries_path, str):
                    view["entries_path"] = raw_entries_path
                if isinstance(payload.source, str):
                    view["source"] = payload.source
                save_json_to_gcs(view, view_object_name)
        except Exception as exc:
            print(f"failed to refresh dashboard view: {exc}")

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
def dashboard(
    world_id: Optional[str] = Query(None, alias="world_id"),
    world: Optional[str] = Query(None, alias="world"),
    top_n: int = Query(limits.API_MAX, ge=1),
) -> Dict[str, Any]:
    selected_world_id = world_id or world or settings.DEFAULT_WORLD_ID
    top_n = min(top_n, limits.API_MAX)
    data = None
    legacy_data = None
    data_source: Optional[str] = None

    try:
        rows = load_inventory_latest_with_prev(selected_world_id)
        if rows:
            data = _build_dashboard_from_db_rows(rows, top_n, selected_world_id)
            print(
                json.dumps(
                    {
                        "type": "dashboard_source",
                        "source": "db",
                        "world_id": selected_world_id,
                        "rows": len(rows),
                        "ts": time.time(),
                    },
                    ensure_ascii=False,
                )
            )
            data_source = "db"
        else:
            print(
                json.dumps(
                    {
                        "type": "dashboard_source",
                        "source": "db_empty",
                        "world_id": selected_world_id,
                        "rows": 0,
                        "ts": time.time(),
                    },
                    ensure_ascii=False,
                )
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "type": "dashboard_source",
                    "source": "db_error",
                    "world_id": selected_world_id,
                    "error": str(exc),
                    "ts": time.time(),
                },
                ensure_ascii=False,
            )
        )

    if data is None:
        if not settings.GCS_BUCKET:
            raise HTTPException(status_code=503, detail="GCS_BUCKET is not configured")

        data_source = "gcs"

        view_object_name = _dashboard_view_object_name()
        legacy_object_name = _latest_object_name()
        try:
            view_data = load_json_from_gcs(view_object_name)
        except Exception as exc:
            print(f"failed to load dashboard view from GCS: {exc}")
            view_data = None

        if isinstance(view_data, dict):
            data = view_data

        if data is None:
            try:
                legacy_data = load_json_from_gcs(legacy_object_name)
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"failed to load latest dashboard from GCS: gs://{settings.GCS_BUCKET}/{legacy_object_name}: {exc}",
                )
            if legacy_data is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"latest dashboard not found: gs://{settings.GCS_BUCKET}/{legacy_object_name}",
                )
            if not isinstance(legacy_data, dict):
                raise HTTPException(status_code=500, detail="latest dashboard payload is invalid")
            data = legacy_data
        else:
            if "top" not in data:
                try:
                    legacy_data = load_json_from_gcs(legacy_object_name)
                except Exception as exc:
                    print(f"failed to load legacy dashboard payload: {exc}")
                    legacy_data = None
                if isinstance(legacy_data, dict):
                    for key in (
                        "top",
                        "top_amount_items", "top_amount_fluids", "top_amount_gases",
                        "top_growth_per_min_items", "top_growth_per_min_fluids", "top_growth_per_min_gases",
                        "top_decrease_per_min_items", "top_decrease_per_min_fluids", "top_decrease_per_min_gases",
                    ):
                        if key in legacy_data and key not in data:
                            data[key] = legacy_data[key]
                    if "source" not in data and isinstance(legacy_data.get("source"), str):
                        data["source"] = legacy_data["source"]
                    if "gcs_path" not in data and isinstance(legacy_data.get("gcs_path"), str):
                        data["gcs_path"] = legacy_data["gcs_path"]
                    if "entries_path" not in data and isinstance(legacy_data.get("entries_path"), str):
                        data["entries_path"] = legacy_data["entries_path"]

        print(
            json.dumps(
                {
                    "type": "dashboard_source",
                    "source": "gcs",
                    "world_id": selected_world_id,
                    "ts": time.time(),
                },
                ensure_ascii=False,
            )
        )

    if "gcs_path" not in data and isinstance(data.get("entries_path"), str):
        data["gcs_path"] = data["entries_path"]
    data.setdefault("bucket", settings.GCS_BUCKET)
    prefix = settings.GCS_PREFIX.strip("/")
    if prefix:
        data.setdefault("prefix", prefix)
    data.setdefault("world_id", selected_world_id)
    if data_source == "gcs":
        data.setdefault("source", "gcs")
    data.setdefault("rows", len(data.get("top_amount") or []))
    data.setdefault("note", {})
    ts_value = data.get("ts")
    try:
        ts_num = float(ts_value) if ts_value is not None else None
    except (TypeError, ValueError):
        ts_num = None
    if ts_num is not None:
        data.setdefault("updated_sec_ago", max(0, int(time.time() - ts_num)))

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
    return JSONResponse(data, headers={"Cache-Control": "no-store"})

@router.post("/jobs/aggregate")
def jobs_aggregate(
    top_n: int = Query(50, ge=1),
    ts: Optional[float] = Query(None),
    _payload: AggregatePayload = Depends(aggregate_guard),
) -> Dict[str, Any]:
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
        if isinstance(latest_payload, dict):
            if isinstance(latest_payload.get("gcs_path"), str):
                view["gcs_path"] = latest_payload["gcs_path"]
            if isinstance(latest_payload.get("entries_path"), str):
                view["entries_path"] = latest_payload["entries_path"]
            if isinstance(latest_payload.get("source"), str):
                view["source"] = latest_payload["source"]
        if "entries_path" not in view and isinstance(entries_source, str):
            view["entries_path"] = entries_source
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
