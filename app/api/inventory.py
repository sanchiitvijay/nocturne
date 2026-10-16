"""Devices, sites, tickets and the global search behind the command palette."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..cache import cache
from ..config import cfg
from ..security import require
from ..services import analytics, classify, correlate, textmine

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/insights/overview")
def overview(window: str = "7d", start: str | None = None, end: str | None = None,
             user=Depends(require("view_dashboard")), conn=Depends(db.get_conn)):
    try:
        return analytics.overview(conn, window, start, end)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ── devices ──────────────────────────────────────────────────────────────────

@router.get("/devices")
def devices(q: str = "", name: str = "", ip: str = "", model: str = "", role: str = "", site: str = "", sort: str = "events", page: int = 1, size: int = 0,
            user=Depends(require("view_inventory")), conn=Depends(db.get_conn)):
    size = max(1, min(size or cfg.app.page_size, 200))
    where, params = ["1=1"], []

    # Support separate search fields
    if name:
        where.append("d.name LIKE ?")
        params.append(f"%{name}%")
    if ip:
        where.append("d.ip >= ? AND d.ip < ?")
        params += [ip.rstrip("."), ip.rstrip(".") + "\uffff"]
    if model:
        where.append("d.machine_type LIKE ?")
        params.append(f"%{model}%")

    # Legacy single search box
    if q and not (name or ip or model):
        where.append("(d.name LIKE ? OR d.ip LIKE ? OR d.machine_type LIKE ? OR d.site_code = ?)")
        params += [f"%{q}%", f"{q}%", f"%{q}%", textmine.site_code(q) or q]

    if role:
        where.append("d.role = ?")
        params.append(role)
    site_digits = re.sub(r"(?i)^fei[\s-]*", "", site.strip())
    if site_digits:
        where.append("(d.site_code = ? OR d.site_code LIKE ?)")
        params += [textmine.site_code(site_digits) or site_digits, f"{site_digits}%"]
    order = {"events": "d.event_count DESC", "name": "d.name COLLATE NOCASE", "recent": "d.last_seen DESC"}.get(sort, "d.event_count DESC")
    w = " AND ".join(where)
    total = cache.get(conn, "device_count", (q, name, ip, model, role, site), lambda: db.scalar(conn, f"SELECT COUNT(*) FROM devices d WHERE {w}", params, 0))
    # Pick the page first, then compute the per-device figures for those rows only (not for every device before sorting).
    items = db.rows(conn, f"""WITH page AS (SELECT d.id FROM devices d WHERE {w} ORDER BY {order}, d.id LIMIT ? OFFSET ?)
                             SELECT d.id, d.name, d.ip, d.role, d.site_code, d.machine_type, d.vendor, d.event_count, d.last_seen,
                                    d.last_status, s.label site_label,
                                    (SELECT COUNT(DISTINCT ticket_id) FROM ticket_links l WHERE l.device_id=d.id) tickets,
                                    (SELECT transition FROM events e WHERE e.device_id=d.id AND e.pair_key LIKE '%|node'
                                       AND e.transition IS NOT NULL ORDER BY e.ts DESC, e.source_id DESC LIMIT 1) node_state,
                                    (SELECT COUNT(*) FROM events e WHERE e.device_id=d.id AND e.severity='P1') p1
                             FROM page JOIN devices d ON d.id = page.id LEFT JOIN sites s ON s.code=d.site_code
                             ORDER BY {order}, d.id""", params + [size, (max(page, 1) - 1) * size])
    for i in items:
        i["status_label"] = classify.status_label(i["last_status"])
    roles = cache.get(conn, "device_roles", None, lambda: db.rows(conn, "SELECT role, COUNT(*) n FROM devices GROUP BY role ORDER BY n DESC"))
    return {"items": items, "total": total, "page": page, "size": size, "roles": roles}


@router.get("/devices/{device_id}")
def device(device_id: int, user=Depends(require("view_inventory")), conn=Depends(db.get_conn)):
    d = db.one(conn, "SELECT d.*, s.label site_label, s.address site_address FROM devices d LEFT JOIN sites s ON s.code=d.site_code WHERE d.id=?", (device_id,))
    if not d:
        raise HTTPException(404, "Device not found.")
    d["extra"] = db.loads(d["extra"], {})
    d["status_label"] = classify.status_label(d["last_status"])
    by_type = db.rows(conn, """SELECT name, severity, category, COUNT(*) n, MAX(ts) last FROM events WHERE device_id=?
                              GROUP BY name ORDER BY n DESC LIMIT 12""", (device_id,))
    by_day = db.rows(conn, """SELECT substr(ts,1,10) day, COUNT(*) n, SUM(CASE WHEN severity='P1' THEN 1 ELSE 0 END) p1
                             FROM events WHERE device_id=? AND ts IS NOT NULL GROUP BY day ORDER BY day""", (device_id,))
    outs = correlate.outages(conn, device_id=device_id)
    summary = correlate.outage_summary(outs)
    tickets = db.rows(conn, """SELECT t.number, t.kind, t.state, t.is_open, t.created_at, t.short_description, t.resolution,
                                     MAX(l.confidence) confidence, GROUP_CONCAT(DISTINCT l.kind) kinds
                              FROM ticket_links l JOIN tickets t ON t.id=l.ticket_id WHERE l.device_id=?
                              GROUP BY t.id ORDER BY t.created_at DESC LIMIT 20""", (device_id,))
    recent = correlate.timeline(conn, device_id, None)
    peers = db.rows(conn, "SELECT id, name, role, ip FROM devices WHERE site_code=? AND id<>? ORDER BY event_count DESC LIMIT 12",
                    (d["site_code"], device_id)) if d["site_code"] else []
    return {"device": d, "health": correlate.health(conn, device_id, d["last_seen"]), "by_type": by_type, "by_day": by_day,
            "outages": sorted([o for o in outs if o["minutes"] is not None], key=lambda o: o["down_ts"])[-30:],
            "outage_summary": {k: v for k, v in summary.items() if k != "flapping_devices"},
            "flap_cycles": summary["flapping_devices"].get(device_id, 0), "tickets": tickets, "recent": recent[:40], "peers": peers}


# ── sites ────────────────────────────────────────────────────────────────────

@router.get("/sites")
def sites(q: str = "", state: str = "", page: int = 1, size: int = 0, window: str = "all",
          user=Depends(require("view_inventory")), conn=Depends(db.get_conn)):
    size = max(1, min(size or cfg.app.page_size, 200))
    return cache.get(conn, "sites", (q, state, page, size, window), lambda: _sites(conn, q, state, page, size, window))


def _sites(conn, q: str, state: str, page: int, size: int, window: str) -> dict:
    where, params = ["1=1"], []
    if q:
        where.append("(s.code = ? OR s.label LIKE ? OR s.address LIKE ?)")
        params += [textmine.site_code(q) or q, f"%{q}%", f"%{q}%"]
    if state:
        where.append("s.state = ?")
        params.append(state.upper())
    w = " AND ".join(where)
    total = db.scalar(conn, f"SELECT COUNT(*) FROM sites s WHERE {w}", params, 0)
    items = db.rows(conn, f"""WITH ev AS (SELECT site_code, SUM(actionable) alerts, SUM(CASE WHEN severity='P1' THEN 1 ELSE 0 END) p1,
                                              MAX(ts) last_event FROM events WHERE site_code IS NOT NULL GROUP BY site_code),
                                   dv AS (SELECT site_code, COUNT(*) devices FROM devices WHERE site_code IS NOT NULL GROUP BY site_code),
                                   tk AS (SELECT site_code, COUNT(DISTINCT ticket_id) tickets FROM ticket_links WHERE site_code IS NOT NULL GROUP BY site_code)
                              SELECT s.code, s.label, s.city, s.state, s.address, COALESCE(dv.devices, 0) devices, COALESCE(ev.alerts, 0) alerts,
                                     COALESCE(ev.p1, 0) p1, COALESCE(tk.tickets, 0) tickets, ev.last_event
                              FROM sites s LEFT JOIN ev ON ev.site_code=s.code LEFT JOIN dv ON dv.site_code=s.code LEFT JOIN tk ON tk.site_code=s.code
                              WHERE {w} ORDER BY alerts DESC, s.code LIMIT ? OFFSET ?""", params + [size, (max(page, 1) - 1) * size])
    wnd = analytics.resolve_window(conn, window)
    where_e, params_e = analytics._where(wnd, "e")
    states = db.rows(conn, f"""WITH ev AS (SELECT e.site_code, COUNT(*) alerts, SUM(CASE WHEN e.severity='P1' THEN 1 ELSE 0 END) p1
                                          FROM events e WHERE e.actionable=1 AND e.site_code IS NOT NULL AND {where_e} GROUP BY e.site_code)
                               SELECT s.state, COUNT(*) sites, COALESCE(SUM(ev.alerts), 0) alerts, COALESCE(SUM(ev.p1), 0) p1
                               FROM sites s LEFT JOIN ev ON ev.site_code = s.code WHERE s.state IS NOT NULL GROUP BY s.state""", params_e)
    return {"items": items, "total": total, "page": page, "size": size, "states": states}


@router.get("/sites/{code}")
def site(code: str, user=Depends(require("view_inventory")), conn=Depends(db.get_conn)):
    code = textmine.site_code(code) or code
    s = db.one(conn, "SELECT * FROM sites WHERE code=?", (code,))
    if not s:
        raise HTTPException(404, "Site not found.")
    return cache.get(conn, "site", code, lambda: _site(conn, s, code))


def _site(conn, s: dict, code: str) -> dict:
    devices = db.rows(conn, """SELECT d.id, d.name, d.role, d.ip, d.event_count, d.last_seen,
                                      (SELECT transition FROM events e WHERE e.device_id=d.id AND e.pair_key LIKE '%|node'
                                         AND e.transition IS NOT NULL ORDER BY e.ts DESC, e.source_id DESC LIMIT 1) node_state
                               FROM devices d WHERE d.site_code=? ORDER BY d.event_count DESC""", (code,))
    by_cat = db.rows(conn, "SELECT category, COUNT(*) n FROM events WHERE site_code=? AND actionable=1 GROUP BY 1 ORDER BY n DESC", (code,))
    by_day = db.rows(conn, """SELECT substr(ts,1,10) day, COUNT(*) n, SUM(CASE WHEN severity='P1' THEN 1 ELSE 0 END) p1 FROM events
                             WHERE site_code=? AND actionable=1 AND ts IS NOT NULL GROUP BY day ORDER BY day""", (code,))
    tickets = db.rows(conn, """SELECT t.number, t.kind, t.state, t.is_open, t.created_at, t.short_description, t.resolution,
                                     MAX(l.confidence) confidence, GROUP_CONCAT(DISTINCT l.kind) kinds
                              FROM ticket_links l JOIN tickets t ON t.id=l.ticket_id WHERE l.site_code=?
                              GROUP BY t.id ORDER BY t.created_at DESC LIMIT 25""", (code,))
    recent = db.rows(conn, """SELECT id, ts, name, severity, category, device_name, transition, state, message FROM events
                             WHERE site_code=? AND actionable=1 ORDER BY ts DESC, source_id DESC LIMIT 30""", (code,))
    return {"site": s, "devices": devices, "by_category": by_cat, "by_day": by_day, "tickets": tickets, "recent": recent}


# ── tickets ──────────────────────────────────────────────────────────────────

@router.get("/tickets")
def tickets(q: str = "", number: str = "", description: str = "", work_notes: str = "", kind: str = "", status: str = "", linked: str = "", page: int = 1, size: int = 0,
            user=Depends(require("view_tickets")), conn=Depends(db.get_conn)):
    size = max(1, min(size or cfg.app.page_size, 200))
    where, params = ["1=1"], []

    # Support separate search fields
    if number:
        where.append("t.number LIKE ?")
        params.append(f"%{number}%")

    if description:
        where.append("t.short_description LIKE ?")
        params.append(f"%{description}%")

    if work_notes:
        where.append("t.work_notes LIKE ?")
        params.append(f"%{work_notes}%")

    # Legacy single search box
    if q and not (number or description or work_notes):
        terms = re.findall(r"\w+", q)
        if terms:
            where.append("(t.number LIKE ? OR t.id IN (SELECT rowid FROM tickets_fts WHERE tickets_fts MATCH ?))")
            params += [f"%{q}%", " AND ".join(f'"{x}"*' for x in terms)]
    if kind:
        where.append("t.kind = ?")
        params.append(kind)
    if status in ("open", "closed"):
        where.append("t.is_open = ?")
        params.append(1 if status == "open" else 0)
    if linked in ("yes", "no"):
        where.append(("" if linked == "yes" else "NOT ") + "EXISTS (SELECT 1 FROM ticket_links l WHERE l.ticket_id=t.id)")
    w = " AND ".join(where)
    total = db.scalar(conn, f"SELECT COUNT(*) FROM tickets t WHERE {w}", params, 0)
    items = db.rows(conn, f"""SELECT t.id, t.number, t.kind, t.state, t.is_open, t.priority, t.assignment_group, t.assigned_to,
                                    t.created_at, t.closed_at, t.resolve_minutes, t.short_description, t.resolution,
                                    t.sites, (SELECT COUNT(*) FROM ticket_links l WHERE l.ticket_id=t.id) links,
                                    (SELECT MAX(confidence) FROM ticket_links l WHERE l.ticket_id=t.id) best_link
                             FROM tickets t WHERE {w} ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
                    params + [size, (max(page, 1) - 1) * size])
    for i in items:
        i["sites"] = db.loads(i["sites"], [])
    kinds = db.rows(conn, "SELECT kind, COUNT(*) n FROM tickets GROUP BY kind ORDER BY n DESC")
    return {"items": items, "total": total, "page": page, "size": size, "kinds": kinds}


@router.get("/tickets/{number}")
def ticket(number: str, user=Depends(require("view_tickets")), conn=Depends(db.get_conn)):
    t = db.one(conn, "SELECT * FROM tickets WHERE number=?", (number.upper(),))
    if not t:
        raise HTTPException(404, "Ticket not found.")
    for key in ("sites", "ips", "devices"):
        t[key] = db.loads(t[key], [])
    t["extra"] = db.loads(t["extra"], {})
    t["entries"] = textmine.parse_work_notes(t["work_notes"])
    t["fixes"] = textmine.action_sentences(t["close_notes"] or t["work_notes"], 4, 0 if t["is_open"] else 1.5)
    links = db.rows(conn, """SELECT l.kind, l.value, l.confidence, l.site_code, l.evidence, l.gap_minutes, l.event_id,
                                   e.name event_name, e.severity event_severity, e.ts event_ts,
                                   d.id device_id, d.name device_name, d.role, s.label site_label
                            FROM ticket_links l LEFT JOIN devices d ON d.id = NULLIF(l.device_id, 0)
                            LEFT JOIN sites s ON s.code = l.site_code LEFT JOIN events e ON e.id = l.event_id
                            WHERE l.ticket_id=? ORDER BY l.confidence DESC""", (t["id"],))
    coverage = cache.get(conn, "import_coverage", None, lambda: db.one(conn, "SELECT MIN(ts) first, MAX(ts) last FROM events WHERE source='import'"))
    return {"ticket": t, "links": links, "event_coverage": coverage}


# ── global search (command palette) ──────────────────────────────────────────

@router.get("/search")
def search(q: str, user=Depends(require("view_alerts")), conn=Depends(db.get_conn)):
    q = q.strip()
    if len(q) < 2:
        return {"devices": [], "sites": [], "tickets": [], "alerts": []}
    like = f"%{q}%"
    site_code = textmine.site_code(q) if re.fullmatch(r"\d{2,5}", q) else None
    out = {
        "devices": db.rows(conn, "SELECT id, name, ip, role, site_code FROM devices WHERE name LIKE ? OR ip LIKE ? "
                                 "ORDER BY event_count DESC LIMIT 6", (like, f"{q}%")),
        "sites": db.rows(conn, "SELECT code, label, address FROM sites WHERE code = ? OR label LIKE ? OR address LIKE ? LIMIT 5",
                         (site_code or q, like, like)),
        "tickets": db.rows(conn, "SELECT number, state, short_description FROM tickets WHERE number LIKE ? OR short_description LIKE ? "
                                 "ORDER BY created_at DESC LIMIT 5", (like, like)),
        "alerts": [],
    }
    terms = re.findall(r"\w+", q)
    if terms:
        out["alerts"] = db.rows(conn, """SELECT e.id, e.ts, e.name, e.severity, e.device_name FROM events e
                                         WHERE e.id IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)
                                         ORDER BY e.ts DESC, e.source_id DESC LIMIT 6""", (" AND ".join(f'"{t}"*' for t in terms),))
    return out
