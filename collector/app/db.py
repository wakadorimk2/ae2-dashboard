from __future__ import annotations

import os
from contextlib import contextmanager
from itertools import islice
from typing import Iterable, Iterator, List, Optional, Tuple, TypeVar

import psycopg

from .models import IngestEntry
import logging

_DB_ENV_KEYS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
_ALLOWED_KINDS = {"item", "fluid", "gas"}
_SQL_BATCH_SIZE = 500

T = TypeVar("T")

logger = logging.getLogger(__name__)


def chunked(iterable: Iterable[T], size: int) -> Iterator[List[T]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    iterator = iter(iterable)
    while True:
        chunk = list(islice(iterator, size))
        if not chunk:
            break
        yield chunk


def _load_db_config() -> dict:
    missing = [key for key in _DB_ENV_KEYS if not os.getenv(key)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"missing required DB env vars: {joined} (example: DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=app DB_USER=app DB_PASSWORD=secret)"
        )
    return {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "sslmode": os.getenv("DB_SSLMODE", "require"),
    }

@contextmanager
def db_connection() -> Iterator[psycopg.Connection]:
    cfg = _load_db_config()
    conn = psycopg.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        sslmode=cfg["sslmode"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inventory_latest_rows(
    entries: Iterable[IngestEntry],
    ts: float,
    world_id: str,
) -> List[Tuple[str, str, str, int, float]]:
    rows: List[Tuple[str, str, str, int, float]] = []
    for entry in entries:
        if entry.kind not in _ALLOWED_KINDS:
            continue
        if entry.amount is not None:
            amount = entry.amount
        elif entry.count is not None:
            amount = entry.count
        else:
            amount = 0
        rows.append((world_id, entry.kind, entry.raw_name, amount, float(ts)))
    return rows


def upsert_inventory_latest(entries: List[IngestEntry], ts: float, world_id: str) -> int:
    rows = inventory_latest_rows(entries, ts, world_id)
    if not rows:
        return 0
    # executemany is simple and stable for now; swap to COPY later if needed.
    query = """
        INSERT INTO public.inventory_latest (world_id, kind, raw_name, amount, ts)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (world_id, kind, raw_name)
        DO UPDATE SET amount = excluded.amount, ts = excluded.ts
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, rows)
    return len(rows)


def update_inventory_latest_prev(
    entries: List[IngestEntry],
    ts: float,
    world_id: str,
) -> Tuple[int, int]:
    rows = inventory_latest_rows(entries, ts, world_id)
    logger.info("DB UPDATE rows=%s world_id=%s ts=%s", len(rows), world_id, ts)
    if not rows:
        return 0, 0

    keys: List[Tuple[str, str, str]] = []
    seen = set()
    for row in rows:
        key = (row[0], row[1], row[2])
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)

    prev_rows = 0
    latest_rows = 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            existing_latest: dict[Tuple[str, str, str], Tuple[int, float]] = {}
            if keys:
                for key_chunk in chunked(keys, _SQL_BATCH_SIZE):
                    placeholders = ", ".join(["(%s, %s, %s)"] * len(key_chunk))
                    select_query = f"""
                        SELECT world_id, kind, raw_name, amount, ts
                        FROM public.inventory_latest
                        WHERE (world_id, kind, raw_name) IN ({placeholders})
                    """
                    params: List[object] = []
                    for key in key_chunk:
                        params.extend(key)
                    cur.execute(select_query, params)
                    for world_val, kind_val, raw_val, amount_val, ts_val in cur.fetchall():
                        existing_latest[(world_val, kind_val, raw_val)] = (amount_val, float(ts_val))

            latest_updates: List[Tuple[str, str, str, int, float]] = []
            prev_updates: List[Tuple[str, str, str, int, float]] = []
            for row in rows:
                key = (row[0], row[1], row[2])
                incoming_amount = row[3]
                incoming_ts = row[4]
                existing = existing_latest.get(key)
                if existing is None:
                    latest_updates.append(row)
                    existing_latest[key] = (incoming_amount, incoming_ts)
                    continue
                existing_amount, existing_ts = existing
                if incoming_ts < existing_ts:
                    continue
                if incoming_ts > existing_ts:
                    prev_updates.append((*key, existing_amount, existing_ts))
                latest_updates.append(row)
                existing_latest[key] = (incoming_amount, incoming_ts)

            if prev_updates:
                for prev_chunk in chunked(prev_updates, _SQL_BATCH_SIZE):
                    placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(prev_chunk))
                    prev_query = f"""
                        INSERT INTO public.inventory_prev (world_id, kind, raw_name, amount_prev, ts_prev)
                        VALUES {placeholders}
                        ON CONFLICT (world_id, kind, raw_name)
                        DO UPDATE SET amount_prev = excluded.amount_prev, ts_prev = excluded.ts_prev
                    """
                    params = []
                    for prev_row in prev_chunk:
                        params.extend(prev_row)
                    cur.execute(prev_query, params)
                    prev_rows += cur.rowcount or 0

            if latest_updates:
                # At this point, latest_updates only contains rows where incoming_ts >= existing_ts
                latest_query = """
                    INSERT INTO public.inventory_latest (world_id, kind, raw_name, amount, ts)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (world_id, kind, raw_name)
                    DO UPDATE SET amount = excluded.amount, ts = excluded.ts
                """
                cur.executemany(latest_query, latest_updates)
                latest_rows = len(latest_updates)

    return prev_rows, latest_rows


def get_inventory_latest_primary_key_columns() -> List[str]:
    query = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = 'inventory_latest'
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [row[0] for row in cur.fetchall()]


def inventory_latest_has_unique_index_on_columns(columns: Tuple[str, ...]) -> bool:
    if not columns:
        return False
    query = """
        SELECT 1
        FROM pg_index idx
        JOIN pg_class tbl ON tbl.oid = idx.indrelid
        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
        WHERE idx.indisunique
          AND ns.nspname = 'public'
          AND tbl.relname = 'inventory_latest'
          AND (
              SELECT array_agg(att.attname ORDER BY key_ords.ord)
              FROM unnest(idx.indkey) WITH ORDINALITY AS key_ords(attnum, ord)
              JOIN pg_attribute att
                ON att.attrelid = idx.indrelid
               AND att.attnum = key_ords.attnum
              WHERE key_ords.attnum > 0
          ) = %s::text[]
        LIMIT 1
    """
    params = [list(columns)]
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone() is not None


def load_inventory_latest_with_prev(
    world_id: str,
) -> List[Tuple[str, str, int, float, Optional[int], Optional[float]]]:
    query = """
        SELECT latest.kind, latest.raw_name, latest.amount, latest.ts, prev.amount_prev, prev.ts_prev
        FROM public.inventory_latest AS latest
        LEFT JOIN public.inventory_prev AS prev
          ON latest.world_id = prev.world_id
         AND latest.kind = prev.kind
         AND latest.raw_name = prev.raw_name
        WHERE latest.world_id = %s
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (world_id,))
            return cur.fetchall()
