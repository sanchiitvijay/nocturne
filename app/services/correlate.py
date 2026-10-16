"""Event correlation: outages (down→up pairs), flapping, blast radius, timelines and health scores."""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta

from .. import db
from ..config import cfg

K = cfg.correlation
FMT = "%Y-%m-%d %H:%M:%S"


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def shift(ts: str, **delta) -> str:
    return (parse_ts(ts) + timedelta(**delta)).strftime(FMT)


def as_of(conn) -> str | None:
    return db.scalar(conn, "SELECT MAX(ts) FROM events")


def pair_outages(rows: list[dict]) -> list[dict]:
    """rows sorted by pair_key, ts → closed outages plus still-open ones (up_ts None)."""
    out, open_down = [], {}
    for r in rows:
        key = r["pair_key"]
        if r["transition"] == "down":
            open_down.setdefault(key, r)  # first down of a streak starts the outage
        elif r["transition"] == "up" and key in open_down:
            d = open_down.pop(key)
            t0, t1 = parse_ts(d["ts"]), parse_ts(r["ts"])
            if t0 and t1:
                out.append({"pair_key": key, "device_id": d["device_id"], "down_id": d["id"], "up_id": r["id"],
                            "down_ts": d["ts"], "up_ts": r["ts"], "minutes": round((t1 - t0).total_seconds() / 60, 1),
                            "name": d["name"]})
    for key, d in open_down.items():
        out.append({"pair_key": key, "device_id": d["device_id"], "down_id": d["id"], "up_id": None,
                    "down_ts": d["ts"], "up_ts": None, "minutes": None, "name": d["name"]})
    return out


def outages(conn, start: str | None = None, end: str | None = None, device_id: int | None = None) -> list[dict]:
    where, params = ["transition IS NOT NULL", "pair_key IS NOT NULL", "ts IS NOT NULL"], []
    if start:
        where.append("ts >= ?")
        params.append(start)
    if end:
        where.append("ts <= ?")
        params.append(end)
    if device_id:
        where.append("device_id = ?")
        params.append(device_id)
    rows = db.rows(conn, f"SELECT id, ts, device_id, pair_key, transition, name FROM events WHERE {' AND '.join(where)} "
                         "ORDER BY pair_key, ts, source_id", params)
    return pair_outages(rows)


def outage_summary(items: list[dict]) -> dict:
    closed = [o["minutes"] for o in items if o["minutes"] is not None]
    flap_counts: dict[int, int] = {}
    for o in items:
        if o["minutes"] is not None and o["minutes"] <= K.flap_window_minutes and o["device_id"]:
            flap_counts[o["device_id"]] = flap_counts.get(o["device_id"], 0) + 1
    flapping = {d: c for d, c in flap_counts.items() if c >= K.flap_threshold}
    return {
        "closed": len(closed),
        "open": sum(1 for o in items if o["minutes"] is None),
        "mttr_minutes": round(statistics.median(closed), 1) if closed else None,
        "p90_minutes": round(sorted(closed)[int(len(closed) * 0.9) - 1], 1) if len(closed) >= 10 else None,
        "flapping_devices": flapping,
    }


def blast_radius(conn, event: dict) -> list[dict]:
    if not event.get("site_code") or not event.get("ts"):
        return []
    lo, hi = shift(event["ts"], minutes=-K.blast_radius_minutes), shift(event["ts"], minutes=K.blast_radius_minutes)
    return db.rows(conn, """SELECT e.id, e.ts, e.name, e.severity, e.device_id, e.device_name, d.role
                            FROM events e LEFT JOIN devices d ON d.id = e.device_id
                            WHERE e.site_code = ? AND e.ts BETWEEN ? AND ? AND e.transition = 'down'
                              AND e.device_id IS NOT NULL AND e.device_id <> COALESCE(?, -1)
                            ORDER BY e.ts, e.source_id LIMIT 40""", (event["site_code"], lo, hi, event.get("device_id")))


def timeline(conn, device_id: int, center: str | None, hours: int | None = None) -> list[dict]:
    hours = hours or K.timeline_hours
    if not center:
        return db.rows(conn, "SELECT id, ts, name, severity, category, transition, message, state FROM events "
                             "WHERE device_id=? ORDER BY ts DESC, source_id DESC LIMIT 60", (device_id,))
    return db.rows(conn, """SELECT id, ts, name, severity, category, transition, message, state FROM events
                            WHERE device_id=? AND ts BETWEEN ? AND ? ORDER BY ts, source_id""",
                   (device_id, shift(center, hours=-hours), shift(center, hours=hours)))


def health(conn, device_id: int, reference: str | None = None) -> dict:
    """0–100 score from recent severity-weighted events, flapping and open tickets."""
    reference = reference or as_of(conn)
    if not reference:
        return {"score": 100, "grade": "Healthy", "parts": {}}
    start = shift(reference, days=-K.health_window_days)
    w = K.health_weights
    counts = {r["severity"]: r["n"] for r in db.rows(conn, "SELECT severity, COUNT(*) n FROM events WHERE device_id=? "
                                                           "AND ts BETWEEN ? AND ? GROUP BY severity", (device_id, start, reference))}
    flaps = outage_summary(outages(conn, start, reference, device_id))["flapping_devices"].get(device_id, 0)
    open_tickets = db.scalar(conn, """SELECT COUNT(DISTINCT t.id) FROM ticket_links l JOIN tickets t ON t.id=l.ticket_id
                                     WHERE l.device_id=? AND t.is_open=1""", (device_id,), 0)
    penalty = sum(counts.get(s, 0) * w.get(s, 0) for s in ("P1", "P2", "P3", "P4")) + flaps * w.flap + open_tickets * w.open_ticket
    score = max(0, round(100 * math.exp(-penalty / 60)))  # smooth decay keeps busy devices distinguishable
    grade = "Healthy" if score >= 80 else "Watch" if score >= 55 else "Degraded" if score >= 30 else "Critical"
    return {"score": score, "grade": grade, "window_days": K.health_window_days,
            "parts": {"events": counts, "flap_cycles": flaps, "open_tickets": open_tickets}}
