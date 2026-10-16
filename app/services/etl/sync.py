"""One resync for every situation: events only, tickets only, both, in any order, re-uploaded or purged.

Everything derived from the stored events and tickets is rebuilt from them, so the result never depends on
upload order: device counters and current attributes, the site registry, ticket links with their time evidence,
and the search indexes.
"""
from __future__ import annotations

import time

from ... import db
from . import linker


def resync(conn, report=None) -> dict:
    started = time.time()
    step = report or (lambda *_: None)

    step(0.1, "Refreshing devices")
    conn.execute("""UPDATE devices SET
        event_count = COALESCE((SELECT COUNT(*) FROM events e WHERE e.device_id = devices.id), 0),
        first_seen  = (SELECT MIN(ts) FROM events e WHERE e.device_id = devices.id),
        last_seen   = (SELECT MAX(ts) FROM events e WHERE e.device_id = devices.id),
        last_status = COALESCE((SELECT status_code FROM events e WHERE e.device_id = devices.id AND status_code IS NOT NULL
                                ORDER BY ts DESC, source_id DESC LIMIT 1), last_status),
        ip          = COALESCE((SELECT ip FROM events e WHERE e.device_id = devices.id AND ip IS NOT NULL
                                ORDER BY ts DESC, source_id DESC LIMIT 1), ip)""")
    devices = db.scalar(conn, "SELECT COUNT(*) FROM devices", default=0)
    silent = db.scalar(conn, "SELECT COUNT(*) FROM devices WHERE event_count = 0", default=0)

    step(0.3, "Checking sites")
    missing = [r["site_code"] for r in db.rows(conn, """SELECT DISTINCT site_code FROM devices
                                                       WHERE site_code IS NOT NULL AND site_code NOT IN (SELECT code FROM sites)""")]
    now = db.now()
    conn.executemany("INSERT OR IGNORE INTO sites(code, updated_at) VALUES (?, ?)", [(s, now) for s in missing])

    step(0.45, "Linking tickets")
    links = linker.relink(conn)
    known_sites = {r["code"] for r in db.rows(conn, "SELECT code FROM sites")}
    waiting = 0  # tickets naming sites that have no events yet: they link once those events are imported
    for r in db.rows(conn, "SELECT sites FROM tickets WHERE id NOT IN (SELECT ticket_id FROM ticket_links)"):
        if any(s not in known_sites for s in (db.loads(r["sites"], []) or [])):
            waiting += 1

    step(0.85, "Rebuilding search")
    db.fts_rebuild(conn)
    db.optimize(conn)
    db.bump_version(conn)

    ev = db.one(conn, "SELECT COUNT(*) n, MIN(ts) first, MAX(ts) last FROM events WHERE source='import'") or {}
    tk = db.one(conn, "SELECT COUNT(*) n, MIN(created_at) first, MAX(created_at) last, SUM(created_at IS NULL) undated FROM tickets") or {}
    return {
        "devices": devices, "devices_without_events": silent, "sites_added": len(missing),
        "events": {"count": ev.get("n") or 0, "first": ev.get("first"), "last": ev.get("last")},
        "tickets": {"count": tk.get("n") or 0, "first": tk.get("first"), "last": tk.get("last"), "undated": tk.get("undated") or 0},
        "linking": links, "tickets_waiting_for_site_events": waiting,
        "seconds": round(time.time() - started, 2),
    }

