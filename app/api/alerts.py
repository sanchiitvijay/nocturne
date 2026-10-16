"""Alert console, triage pipeline (5 stages), alert state, feedback and export."""
from __future__ import annotations

import asyncio
import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import db
from ..bus import bus
from ..cache import cache
from ..config import cfg
from ..security import client_ip, require
from ..services import ai, analytics, classify, diagnostics, recommend, textmine

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
STATES = ("new", "acknowledged", "resolved")
SORTS = {"newest": "e.ts DESC, e.source_id DESC", "oldest": "e.ts ASC, e.source_id ASC", "severity": "e.severity ASC, e.ts DESC, e.source_id DESC"}
_IP_LIKE = re.compile(r"^\d{1,3}(\.\d{1,3}){1,3}\.?$")
_SITE_LIKE = re.compile(r"^(?:fei\s*)?(\d{3,5})$", re.I)


def _multi(value: str | None) -> list[str]:
    return [v for v in (value or "").split(",") if v]


def _int_param(p: dict, key: str) -> int:
    try:
        return int(p[key])
    except (TypeError, ValueError):
        raise HTTPException(400, f"{key} must be a whole number.") from None


_FORMULA_START = frozenset("=+-@\t\r")


def csv_safe(value):
    """Spreadsheet-safe cell: text starting with = + - @ (or a tab/CR) is prefixed so Excel shows it instead of running it."""
    if type(value) is str and value and value[0] in _FORMULA_START:
        return "'" + value
    return value


def build_filter(conn, p: dict, skip: str | None = None) -> tuple[str, list]:
    """Translate query params into SQL. `skip` leaves one dimension out (for facet counts)."""
    where, params = ["1=1"], []

    event_id = (p.get("event_id") or "").strip()
    text = (p.get("text") or "").strip()
    ip = (p.get("ip") or "").strip().rstrip(".")
    device = (p.get("device") or "").strip()
    site = (p.get("site") or "").strip()
    q = (p.get("q") or "").strip()

    if event_id.isdigit():  # the monitoring tool's EventID or NOCTURNE's own alert number
        where.append("(e.source_id = ? OR e.id = ?)")
        params += [int(event_id), int(event_id)]
    if text:
        terms = re.findall(r"\w+", text)
        if terms:
            where.append("e.id IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)")
            params.append(" AND ".join(f'"{t}"*' for t in terms))
    if ip:  # prefix match as typed: "10.14" finds 10.14.x.x and 10.141.x.x
        where.append("e.ip >= ? AND e.ip < ?")
        params += [ip, ip + "\uffff"]
    if device:
        where.append("e.device_name LIKE ?")
        params.append(f"%{device}%")
    site_digits = re.sub(r"(?i)^fei[\s-]*", "", site)
    if site_digits:
        where.append("(e.site_code = ? OR e.site_code LIKE ?)")
        params += [textmine.site_code(site_digits) or site_digits, f"{site_digits}%"]

    # Legacy single search box: try to detect what type of search it is
    if q and not (event_id or text or ip or device or site_digits):
        site_match = _SITE_LIKE.match(q)
        if _IP_LIKE.match(q):
            ip = q.rstrip(".")
            if q.count(".") < 3 or q.endswith("."):
                where.append("(e.ip = ? OR (e.ip >= ? AND e.ip < ?))")
                params += [ip, ip + ".", ip + "/"]
            else:
                where.append("e.ip = ?")
                params.append(ip)
        elif site_match:
            where.append("e.site_code = ?")
            params.append(textmine.site_code(site_match.group(1)))
        elif q.isdigit():
            where.append("e.id = ?")
            params.append(int(q))
        else:
            terms = [t for t in re.findall(r"[\w]+", q) if t]
            if terms:
                where.append("e.id IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)")
                params.append(" AND ".join(f'"{t}"*' for t in terms))
    for key, col in (("severity", "e.severity"), ("category", "e.category"), ("state", "e.state"), ("source", "e.source")):
        values = _multi(p.get(key))
        if values and key != skip:
            where.append(f"{col} IN ({','.join('?' * len(values))})")
            params += values
    for key, col in (("device_id", "e.device_id"), ("type_id", "e.type_id")):
        if p.get(key):
            where.append(f"{col} = ?")
            params.append(_int_param(p, key))
    if p.get("hour", "").isdigit():
        where.append("CAST(strftime('%H', e.ts) AS INTEGER) = ?")
        params.append(int(p["hour"]))
    if p.get("transition"):
        where.append("e.transition = ?")
        params.append(p["transition"])
    if p.get("actionable") in ("1", "0"):
        where.append("e.actionable = ?")
        params.append(int(p["actionable"]))
    window = p.get("window")
    if window and window != "all":
        try:
            w = analytics.resolve_window(conn, window, p.get("from"), p.get("to"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if w.get("start"):
            where.append("e.ts >= ?")
            params.append(w["start"])
        if w.get("end") and window == "custom":
            where.append("e.ts <= ?")
            params.append(w["end"])
    return " AND ".join(where), params


def _enrich(conn, items: list[dict]) -> list[dict]:
    dev_ids = sorted({i["device_id"] for i in items if i.get("device_id")})
    tickets, repeats = {}, {}
    if dev_ids:
        marks = ",".join("?" * len(dev_ids))
        tickets = {r["device_id"]: r["n"] for r in db.rows(conn, f"""SELECT device_id, COUNT(DISTINCT ticket_id) n FROM ticket_links
                                                                    WHERE device_id IN ({marks}) GROUP BY device_id""", dev_ids)}
        repeats = {(r["device_id"], r["type_id"]): r["n"] for r in db.rows(conn, f"""SELECT device_id, type_id, COUNT(*) n FROM events
                                                                    WHERE device_id IN ({marks}) GROUP BY device_id, type_id""", dev_ids)}
    for i in items:
        i["tickets"] = tickets.get(i.get("device_id"), 0)
        i["repeats"] = repeats.get((i.get("device_id"), i.get("type_id")), 1)
        i["status_label"] = classify.status_label(i.get("status_code"))
    return items


CARD_COLUMNS = """e.id, e.source, e.source_id, e.ts, e.type_id, e.name, e.message, e.device_id, e.device_name, e.ip,
                  e.site_code, e.status_code, e.severity, e.category, e.actionable, e.transition, e.state, e.owner, e.state_at,
                  s.label site_label, d.role"""


@router.get("")
def list_alerts(request: Request, page: int = 1, size: int = 0, sort: str = "newest",
                user=Depends(require("view_alerts")), conn=Depends(db.get_conn)):
    p = dict(request.query_params)
    size = max(1, min(size or cfg.app.page_size, 200))
    where, params = build_filter(conn, p)

    def counts():  # the same for every page and sort of this filter, so paging through results reuses them
        facets = {}
        for dim in ("severity", "category", "state", "source"):
            fw, fp = build_filter(conn, p, skip=dim)
            facets[dim] = {r["k"]: r["n"] for r in db.rows(conn, f"SELECT e.{dim} k, COUNT(*) n FROM events e WHERE {fw} GROUP BY 1", fp)}
        return {"total": db.scalar(conn, f"SELECT COUNT(*) FROM events e WHERE {where}", params, 0), "facets": facets,
                "as_of": db.scalar(conn, "SELECT MAX(ts) FROM events")}

    filters = tuple(sorted((k, v) for k, v in p.items() if k not in ("page", "size", "sort")))
    summary = cache.get(conn, "alert_counts", filters, counts)
    items = db.rows(conn, f"""SELECT {CARD_COLUMNS} FROM events e LEFT JOIN sites s ON s.code=e.site_code
                              LEFT JOIN devices d ON d.id=e.device_id WHERE {where}
                              ORDER BY {SORTS.get(sort, SORTS['newest'])} LIMIT ? OFFSET ?""",
                    params + [size, (max(page, 1) - 1) * size])
    return {"items": _enrich(conn, items), "page": page, "size": size, **summary}


@router.get("/export.csv")
def export(request: Request, user=Depends(require("export_data")), conn=Depends(db.get_conn)):
    where, params = build_filter(conn, dict(request.query_params))
    rows = db.rows(conn, f"""SELECT e.id, e.ts, e.severity, e.category, e.name, e.device_name, e.ip, e.site_code, s.label site,
                                    e.transition, e.state, e.owner, e.source, e.source_id, e.message
                             FROM events e LEFT JOIN sites s ON s.code=e.site_code WHERE {where} ORDER BY e.ts DESC, e.source_id DESC LIMIT 100000""", params)
    db.audit(conn, user, "alerts.export", f"{len(rows)} rows", ip=client_ip(request))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(rows[0].keys() if rows else ["id"])
    for r in rows:
        writer.writerow([csv_safe(v) for v in r.values()])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=nocturne-alerts.csv"})


def _load(conn, event_id: int) -> tuple[dict, dict | None, dict | None]:
    event = db.one(conn, f"SELECT {CARD_COLUMNS}, e.extra, e.job_id, e.state_note FROM events e LEFT JOIN sites s ON s.code=e.site_code "
                         "LEFT JOIN devices d ON d.id=e.device_id WHERE e.id=?", (event_id,))
    if not event:
        raise HTTPException(404, "That alert does not exist (it may have been purged).")
    event["extra"] = db.loads(event["extra"], {})
    event["status_label"] = classify.status_label(event["status_code"])
    event["severity_label"] = classify.severity_label(event["severity"])
    device = db.one(conn, "SELECT * FROM devices WHERE id=?", (event["device_id"],)) if event["device_id"] else None
    site = db.one(conn, "SELECT * FROM sites WHERE code=?", (event["site_code"],)) if event["site_code"] else None
    return event, device, site


@router.get("/{event_id}")
def alert_detail(event_id: int, user=Depends(require("view_alerts")), conn=Depends(db.get_conn)):
    event, device, site = _load(conn, event_id)
    feedback = db.rows(conn, "SELECT username, verdict, ticket_number, note, created_at FROM feedback WHERE event_id=? ORDER BY id DESC", (event_id,))
    return {"event": event, "device": device, "site": site, "feedback": feedback, "ai": ai.status(),
            "diagnostics_mode": cfg.diagnostics.mode}


# Stages 2, 3 and 5 share the same analysis and ticket ranking; each is computed once per alert and data version.

def _analysis(conn, event: dict, device: dict | None) -> dict:
    return cache.get(conn, "triage_analysis", event["id"], lambda: recommend.analysis(conn, event, device))


def _history(conn, event: dict, device: dict | None) -> list[dict]:
    return cache.get(conn, "triage_history", event["id"], lambda: recommend.related_tickets(conn, event, device))


@router.get("/{event_id}/analysis")
def stage_analysis(event_id: int, user=Depends(require("investigate")), conn=Depends(db.get_conn)):
    event, device, site = _load(conn, event_id)
    from ..services import correlate
    out = dict(_analysis(conn, event, device))  # copy: the cached value is shared
    out["health"] = correlate.health(conn, device["id"], event.get("ts")) if device else None
    return out


@router.get("/{event_id}/history")
def stage_history(event_id: int, user=Depends(require("investigate")), conn=Depends(db.get_conn)):
    event, device, _ = _load(conn, event_id)
    return {"tickets": _history(conn, event, device), "timing": recommend.time_context(conn, event)}


async def _checks_for(event: dict, device: dict | None, pace: bool = True) -> dict | None:
    host = (device or {}).get("ip") or event.get("ip") or (device or {}).get("name")
    if not host or not diagnostics.valid_host(host):
        return None
    return await diagnostics.run_checks(host, pace=pace)


@router.post("/{event_id}/checks")
async def stage_checks(event_id: int, user=Depends(require("run_diagnostics"))):
    with db.session() as conn:
        event, device, _ = _load(conn, event_id)
    result = await _checks_for(event, device)
    if not result:
        raise HTTPException(422, "This alert has no device IP or host name to check.")
    return result


async def _recommendation(event_id: int, user: dict, ask_ai: bool = False, refresh: bool = False) -> dict:
    """Built-in engine first; Gemini on top when configured for this alert (cached), with a labelled fallback."""
    with db.session() as conn:
        event, device, site = _load(conn, event_id)
    checks = await _checks_for(event, device, pace=False)  # no UI is watching this check run, so no pacing delay
    with db.session() as conn:
        analysis = _analysis(conn, event, device)
        history = _history(conn, event, device)
        engine = recommend.build(conn, event, device, site, analysis, history, checks)
    engine["source"] = "engine"
    engine["ai"] = ai.status()
    use_ai = ask_ai or refresh or ai.wants_auto(event)
    if not use_ai:
        return engine
    if (ask_ai or refresh) and user["role"] not in cfg.permissions.ai_refine:
        raise HTTPException(403, "Your role does not allow AI requests.")
    ctx = ai.context(event, device, site, analysis, history, checks, engine)
    try:
        with db.session() as conn:
            result = await asyncio.to_thread(ai.insight, conn, ctx, refresh)
            if refresh:
                db.audit(conn, user, "ai.refresh", str(event_id), ai.label())
    except ai.AIUnavailable as exc:
        return {**engine, "source": "fallback", "fallback_reason": str(exc)}
    return ai.merge(engine, result["payload"], result["cache"], refresh)


@router.get("/{event_id}/recommendation")
async def stage_recommendation(event_id: int, user=Depends(require("investigate"))):
    return await _recommendation(event_id, user)


class AiAsk(BaseModel):
    refresh: bool = False


@router.post("/{event_id}/ai")
async def ask_ai(event_id: int, body: AiAsk, user=Depends(require("ai_refine"))):
    """Ask Gemini now (on-demand mode or lower severities); refresh=true ignores the cache."""
    return await _recommendation(event_id, user, ask_ai=True, refresh=body.refresh)


class StateChange(BaseModel):
    state: str
    note: str | None = None


@router.post("/{event_id}/state")
def set_state(event_id: int, body: StateChange, request: Request, user=Depends(require("update_alert_state")), conn=Depends(db.get_conn)):
    return _apply_state(conn, [event_id], body.state, body.note, user, request)


class BulkState(BaseModel):
    ids: list[int]
    state: str
    note: str | None = None


@router.post("/bulk-state")
def bulk_state(body: BulkState, request: Request, user=Depends(require("update_alert_state")), conn=Depends(db.get_conn)):
    if not body.ids or len(body.ids) > 500:
        raise HTTPException(400, "Select between 1 and 500 alerts.")
    return _apply_state(conn, body.ids, body.state, body.note, user, request)


def _apply_state(conn, ids: list[int], state: str, note: str | None, user: dict, request: Request) -> dict:
    if state not in STATES:
        raise HTTPException(400, f"State must be one of: {', '.join(STATES)}.")
    ids = sorted(set(ids))
    marks = ",".join("?" * len(ids))
    found = [r["id"] for r in db.rows(conn, f"SELECT id FROM events WHERE id IN ({marks})", ids)]
    if not found:
        raise HTTPException(404, "That alert does not exist (it may have been purged)." if len(ids) == 1
                            else "None of the selected alerts exist any more.")
    marks = ",".join("?" * len(found))
    conn.execute(f"UPDATE events SET state=?, owner=?, state_note=COALESCE(?, state_note), state_at=? WHERE id IN ({marks})",
                 [state, user["username"], (note or "").strip() or None, db.now(), *found])
    db.bump_version(conn)
    db.audit(conn, user, f"alert.{state}", ",".join(map(str, found[:20])), note or "", client_ip(request))
    conn.commit()
    for i in found[:50]:
        bus.publish("alert_state", {"id": i, "state": state, "owner": user["username"]})
    return {"ok": True, "updated": len(found), "missing": len(ids) - len(found), "state": state}


class Feedback(BaseModel):
    verdict: str
    ticket_number: str | None = None
    note: str | None = None


@router.post("/{event_id}/feedback")
def feedback(event_id: int, body: Feedback, request: Request, user=Depends(require("give_feedback")), conn=Depends(db.get_conn)):
    if body.verdict not in ("helpful", "not_helpful"):
        raise HTTPException(400, "Verdict must be helpful or not_helpful.")
    _load(conn, event_id)
    conn.execute("INSERT INTO feedback(event_id, username, verdict, ticket_number, note, created_at) VALUES (?,?,?,?,?,?)",
                 (event_id, user["username"], body.verdict, body.ticket_number, (body.note or "")[:1000], db.now()))
    db.bump_version(conn)  # "marked helpful" changes ticket ranking, so cached triage results must refresh
    db.audit(conn, user, "alert.feedback", str(event_id), f"{body.verdict} {body.ticket_number or ''}", client_ip(request))
    return {"ok": True}


