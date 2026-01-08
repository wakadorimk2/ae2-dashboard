from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Tuple

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


def inventory_latest_rows(entries: Iterable[IngestEntry], ts: float) -> List[Tuple[str, str, int, float]]:
    rows: List[Tuple[str, str, int, float]] = []
    for entry in entries:
        if entry.kind not in _ALLOWED_KINDS:
            continue
        if entry.amount is not None:
            amount = entry.amount
        elif entry.count is not None:
            amount = entry.count
        else:
            amount = 0
        rows.append((entry.kind, entry.raw_name, amount, float(ts)))
    return rows


def upsert_inventory_latest(entries: List[IngestEntry], ts: float) -> int:
    rows = inventory_latest_rows(entries, ts)
    if not rows:
        return 0
    # executemany is simple and stable for now; swap to COPY later if needed.
    query = """
        INSERT INTO public.inventory_latest (kind, raw_name, amount, ts)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (kind, raw_name)
        DO UPDATE SET amount = excluded.amount, ts = excluded.ts
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, rows)
    return len(rows)
