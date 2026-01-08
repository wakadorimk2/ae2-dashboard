from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Optional, Tuple

import psycopg

from .models import IngestEntry

_DB_ENV_KEYS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
_ALLOWED_KINDS = {"item", "fluid", "gas"}


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
            if keys:
                placeholders = ", ".join(["(%s, %s, %s)"] * len(keys))
                prev_query = f"""
                    INSERT INTO public.inventory_prev (world_id, kind, raw_name, amount_prev, ts_prev)
                    SELECT latest.world_id, latest.kind, latest.raw_name, latest.amount, latest.ts
                    FROM public.inventory_latest AS latest
                    JOIN (VALUES {placeholders}) AS incoming(world_id, kind, raw_name)
                      ON latest.world_id = incoming.world_id
                     AND latest.kind = incoming.kind
                     AND latest.raw_name = incoming.raw_name
                    ON CONFLICT (world_id, kind, raw_name)
                    DO UPDATE SET amount_prev = excluded.amount_prev, ts_prev = excluded.ts_prev
                """
                params: List[object] = []
                for key in keys:
                    params.extend(key)
                cur.execute(prev_query, params)
                prev_rows = cur.rowcount or 0

            latest_query = """
                INSERT INTO public.inventory_latest (world_id, kind, raw_name, amount, ts)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (world_id, kind, raw_name)
                DO UPDATE SET amount = excluded.amount, ts = excluded.ts
            """
            cur.executemany(latest_query, rows)
            latest_rows = len(rows)
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
