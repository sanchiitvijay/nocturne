"""SQLite access: one connection per request/thread, WAL for concurrent reads during imports."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import cfg

SCHEMA = Path(__file__).with_name("schema.sql")
_version_lock = threading.Lock()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(cfg.storage.database, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL")  # WAL is a persistent database setting, applied once in init()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_conn():
    """FastAPI dependency."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Columns added to existing tables after their first release; init() adds them in place.
ADDED_COLUMNS = {"ticket_links": {"evidence": "TEXT", "gap_minutes": "INTEGER", "event_id": "INTEGER"},
                 "tickets": {"incident_start": "TEXT"}}


def init() -> None:
    with session() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        for table, cols in ADDED_COLUMNS.items():
            have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, kind in cols.items():
                if have and col not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
        conn.executescript(SCHEMA.read_text())


# ── tiny query helpers ────────────────────────────────────────────────────────

def rows(conn, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def scalar(conn, sql: str, params=(), default=None):
    r = conn.execute(sql, params).fetchone()
    return r[0] if r and r[0] is not None else default


def loads(value, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def dumps(value) -> str | None:
    if value is None or value == {} or value == []:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


# ── data version: bumps on every write so analytic caches stay correct ─────────

def data_version(conn) -> int:
    return int(scalar(conn, "SELECT value FROM meta WHERE key='data_version'", default=0))


def bump_version(conn) -> int:
    with _version_lock:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES('data_version', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1"
        )
        return data_version(conn)


def audit(conn, user: dict | None, action: str, target: str = "", detail: str = "", ip: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log(at, user_id, username, action, target, detail, ip) VALUES (?,?,?,?,?,?,?)",
        (now(), (user or {}).get("id"), (user or {}).get("username", "system"), action, target, detail[:2000], ip),
    )


def fts_index_event(conn, event_id: int) -> None:
    conn.execute(
        "INSERT INTO events_fts(rowid, name, message, device_name) SELECT id, name, message, device_name FROM events WHERE id=?",
        (event_id,),
    )


def optimize(conn) -> None:
    """Refresh the query planner's statistics after bulk changes, so it keeps choosing the covering indexes."""
    conn.execute("PRAGMA analysis_limit=1000")
    conn.execute("PRAGMA optimize")


def fts_rebuild(conn) -> None:
    conn.execute("INSERT INTO events_fts(events_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO tickets_fts(tickets_fts) VALUES('rebuild')")
