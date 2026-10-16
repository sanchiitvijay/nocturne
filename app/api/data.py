"""Data Studio: uploads → mapping review → background import, the event catalogue and housekeeping."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import db
from ..bus import bus
from ..cache import cache
from ..config import cfg
from ..security import client_ip, require
from .alerts import csv_safe
from ..services import classify
from ..services.etl import mapping, readers, sync
from ..services.etl.events import type_overrides
from ..services.etl.runner import job_view, runner

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/uploads")
async def upload(request: Request, files: list[UploadFile] = File(...), user=Depends(require("ingest_data"))):
    staged, limit = [], cfg.storage.max_upload_mb * 1024 * 1024
    for f in files:
        if Path(f.filename or "").suffix.lower() not in readers.SUPPORTED:
            raise HTTPException(400, f"{f.filename}: use CSV, TSV, TXT or XLSX files.")
        chunks, size = [], 0
        while chunk := await f.read(1024 * 1024):  # stop reading as soon as the limit is passed
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, f"{f.filename} is larger than {cfg.storage.max_upload_mb} MB.")
            chunks.append(chunk)
        content = b"".join(chunks)
        if not content.strip():
            raise HTTPException(400, f"{f.filename} is empty.")
        with db.session() as conn:
            try:
                job = runner.stage(conn, f.filename, content, user)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            db.audit(conn, user, "data.upload", f.filename, f"{len(content):,} bytes, detected {job['dataset']}", client_ip(request))
        staged.append(job)
    # Events first, so ticket linking can see the devices they introduce.
    staged.sort(key=lambda j: 0 if j["dataset"] == "events" else 1)
    return {"jobs": staged}


@router.get("/jobs")
def jobs(user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    rows = db.rows(conn, "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50")
    out = []
    for r in rows:
        v = job_view(r)
        v.pop("preview", None)
        out.append(v)
    return {"jobs": out}


@router.get("/jobs/{job_id}")
def job(job_id: str, user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    row = db.one(conn, "SELECT * FROM jobs WHERE id=?", (job_id,))
    if not row:
        raise HTTPException(404, "Import not found.")
    v = job_view(row)
    v["fields"] = {"events": mapping.FIELD_HELP["events"], "tickets": mapping.FIELD_HELP["tickets"]}
    v["reject_count"] = db.scalar(conn, "SELECT COUNT(*) FROM job_rejects WHERE job_id=?", (job_id,), 0)
    return v


class RunJob(BaseModel):
    dataset: str
    mapping: dict[str, int | None]
    options: dict = {}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str, body: RunJob, request: Request, user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    try:
        job = runner.submit(conn, job_id, body.dataset, body.mapping, body.options)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.audit(conn, user, "data.import_started", job["filename"], body.dataset, client_ip(request))
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request, user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    row = db.one(conn, "SELECT status, filename FROM jobs WHERE id=?", (job_id,))
    if not row:
        raise HTTPException(404, "Import not found.")
    if row["status"] not in ("queued", "running"):
        raise HTTPException(409, "Only a queued or running import can be cancelled.")
    runner.cancel(job_id)
    db.audit(conn, user, "data.import_cancelled", row["filename"], ip=client_ip(request))
    return {"ok": True}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, request: Request, user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    row = db.one(conn, "SELECT status, stored_path, filename FROM jobs WHERE id=?", (job_id,))
    if not row:
        raise HTTPException(404, "Import not found.")
    if row["status"] in ("queued", "running"):
        raise HTTPException(409, "Cancel the import before removing it.")
    Path(row["stored_path"]).unlink(missing_ok=True)
    conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    db.audit(conn, user, "data.job_removed", row["filename"], ip=client_ip(request))
    return {"ok": True}


@router.get("/jobs/{job_id}/rejects.csv")
def rejects(job_id: str, user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    rows = db.rows(conn, "SELECT row_no, reason, raw FROM job_rejects WHERE job_id=? ORDER BY row_no", (job_id,))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "reason", "raw"])
    for r in rows:
        w.writerow([r["row_no"], csv_safe(r["reason"]), csv_safe(r["raw"])])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=rejected-rows-{job_id}.csv"})


# ── event catalogue ───────────────────────────────────────────────────────────

@router.get("/catalog")
def catalog(user=Depends(require("manage_catalog")), conn=Depends(db.get_conn)):
    stats = cache.get(conn, "catalog_stats", None, lambda: {r["type_id"]: r for r in db.rows(conn, """SELECT type_id, COUNT(*) n,
                    MIN(severity) worst, MAX(category) category, SUM(actionable) actionable FROM events WHERE type_id IS NOT NULL
                    GROUP BY type_id""")})
    types = db.rows(conn, "SELECT * FROM event_types ORDER BY type_id")
    for t in types:
        s = stats.get(t["type_id"], {})
        t["display_name"] = t["name"] or classify.catalog_name(t["type_id"]) or t["source_name"] or f"EventType-{t['type_id']}"
        t["events"] = s.get("n", 0)
        t["actionable"] = s.get("actionable", 0)
        t["rule_category"] = s.get("category")
        t["rule_severity"] = s.get("worst")
    types.sort(key=lambda t: -t["events"])
    return {"types": types, "severities": dict(cfg.classification.severity_labels.items()), "categories": classify.CATEGORIES}


class CatalogEdit(BaseModel):
    name: str | None = None
    severity: str | None = None
    category: str | None = None


@router.put("/catalog/{type_id}")
def edit_type(type_id: int, body: CatalogEdit, request: Request, user=Depends(require("manage_catalog")), conn=Depends(db.get_conn)):
    if body.severity and body.severity not in classify.SEVERITIES:
        raise HTTPException(400, "Severity must be P1–P4 or blank.")
    if body.category and body.category not in classify.CATEGORIES:
        raise HTTPException(400, "Unknown category.")
    before = db.one(conn, "SELECT name FROM event_types WHERE type_id=?", (type_id,)) or {}
    fallback = classify.catalog_name(type_id) or f"EventType-{type_id}"
    old_display, new_display = before.get("name") or fallback, (body.name or "").strip() or fallback
    conn.execute("""INSERT INTO event_types(type_id, name, severity, category, updated_at) VALUES (?,?,?,?,?)
                    ON CONFLICT(type_id) DO UPDATE SET name=excluded.name, severity=excluded.severity,
                    category=excluded.category, updated_at=excluded.updated_at""",
                 (type_id, (body.name or "").strip() or None, body.severity or None, body.category or None, db.now()))
    # Events that carried the derived name follow the rename; names that came explicitly from the export are kept.
    conn.execute("UPDATE events SET name=? WHERE type_id=? AND name IN (?, ?)", (new_display, type_id, old_display, f"EventType-{type_id}"))
    # Re-classify that type's events so every screen reflects the change at once.
    overrides = type_overrides(conn)
    updates = []
    for r in db.rows(conn, "SELECT id, name, message FROM events WHERE type_id=?", (type_id,)):
        c = classify.classify(type_id, r["name"], r["message"], overrides)
        updates.append((r["name"], c["severity"], c["category"], c["actionable"], r["id"]))
    conn.executemany("UPDATE events SET name=?, severity=?, category=?, actionable=? WHERE id=?", updates)
    db.fts_rebuild(conn)
    db.bump_version(conn)
    db.audit(conn, user, "catalog.edit", str(type_id), body.model_dump_json(), client_ip(request))
    bus.publish("data", {"reason": "catalog"})
    return {"ok": True, "events_updated": len(updates)}


# ── housekeeping ────────────────────────────────────────────────────────────

@router.post("/resync")
def resync(request: Request, user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    """Rebuild everything derived from the stored events and tickets (counters, sites, links, time evidence, search)."""
    result = sync.resync(conn)
    l = result["linking"]
    db.audit(conn, user, "data.resync", "", f"{l['tickets_linked']} of {l['tickets_total']} tickets linked, {l['links']} links", client_ip(request))
    conn.commit()
    bus.publish("data", {"reason": "resync"})
    return result


class Purge(BaseModel):
    scope: str
    confirm: str


# scope: (label, description, statements)
PURGES = {
    "simulated": ("Simulated and custom alerts", "Removes alerts created by the simulator and custom triggers.",
                  ["DELETE FROM events WHERE source IN ('simulation','custom')",
                   # devices a custom alert created, now without any event (counters are stale until resync)
                   "DELETE FROM devices WHERE json_extract(extra, '$.created_by') = 'custom alert' "
                   "AND id NOT IN (SELECT DISTINCT device_id FROM events WHERE device_id IS NOT NULL)"]),
    "alert_states": ("Alert states and feedback", "Sets every alert back to New and clears feedback and AI notes.",
                     ["UPDATE events SET state='new', owner=NULL, state_note=NULL, state_at=NULL",
                      "DELETE FROM feedback", "DELETE FROM ai_insights"]),
    "tickets": ("All tickets", "Removes all tickets and their links.", ["DELETE FROM ticket_links", "DELETE FROM tickets"]),
    "everything": ("All network data", "Removes events, devices, sites, tickets and the catalogue. Users and audit stay.",
                   ["DELETE FROM ticket_links", "DELETE FROM tickets", "DELETE FROM feedback", "DELETE FROM ai_insights",
                    "DELETE FROM events", "DELETE FROM devices", "DELETE FROM sites", "DELETE FROM event_types"]),
}
PURGE_CONFIRM = "PURGE"


@router.get("/purges")
def purge_scopes(user=Depends(require("purge_data"))):
    return {"scopes": [{"scope": k, "label": label, "description": text, "destructive_all": k == "everything"}
                       for k, (label, text, _) in PURGES.items()], "confirm_word": PURGE_CONFIRM}


@router.post("/purge")
def purge(body: Purge, request: Request, user=Depends(require("purge_data")), conn=Depends(db.get_conn)):
    if body.scope not in PURGES:
        raise HTTPException(400, "Unknown purge scope.")
    if body.confirm.strip().upper() != PURGE_CONFIRM:
        raise HTTPException(400, f"Type {PURGE_CONFIRM} to confirm.")
    label, _, statements = PURGES[body.scope]
    for sql in statements:
        conn.execute(sql)
    # Feedback and AI answers about alerts that no longer exist.
    conn.execute("DELETE FROM feedback WHERE event_id NOT IN (SELECT id FROM events)")
    conn.execute("DELETE FROM ai_insights WHERE event_id NOT IN (SELECT id FROM events)")
    sync.resync(conn)
    db.audit(conn, user, "data.purge", body.scope, label, client_ip(request))
    conn.commit()
    conn.execute("VACUUM") if body.scope == "everything" else None
    bus.publish("data", {"reason": "purge", "scope": body.scope})
    return {"ok": True, "purged": label}


def _overlap_days(conn) -> int | None:
    """Days where imported events and ticket opening dates coincide; time-based matching only works inside them."""
    r = db.one(conn, """SELECT MAX(a.first, b.first) lo, MIN(a.last, b.last) hi FROM
                        (SELECT MIN(ts) first, MAX(ts) last FROM events WHERE source='import') a,
                        (SELECT MIN(created_at) first, MAX(created_at) last FROM tickets) b""")
    if not r or not r["lo"] or not r["hi"]:
        return None
    return max(0, db.scalar(conn, "SELECT CAST(julianday(date(?)) - julianday(date(?)) AS INTEGER) + 1", (r["hi"], r["lo"]), 0))


@router.get("/summary")
def summary(user=Depends(require("ingest_data")), conn=Depends(db.get_conn)):
    out = cache.get(conn, "data_summary", None, lambda: _summary(conn))
    return {**out, "db_mb": round(Path(cfg.storage.database).stat().st_size / 1048576, 1) if Path(cfg.storage.database).exists() else 0}


def _summary(conn) -> dict:
    return {
        "events": db.scalar(conn, "SELECT COUNT(*) FROM events", default=0),
        "by_source": {r["source"]: r["n"] for r in db.rows(conn, "SELECT source, COUNT(*) n FROM events GROUP BY source")},
        "range": db.one(conn, "SELECT MIN(ts) first, MAX(ts) last FROM events"),
        "ticket_range": db.one(conn, "SELECT MIN(created_at) first, MAX(created_at) last FROM tickets"),
        "overlap_days": _overlap_days(conn),
        "devices": db.scalar(conn, "SELECT COUNT(*) FROM devices", default=0),
        "devices_with_site": db.scalar(conn, "SELECT COUNT(*) FROM devices WHERE site_code IS NOT NULL", default=0),
        "sites": db.scalar(conn, "SELECT COUNT(*) FROM sites", default=0),
        "event_types": db.scalar(conn, "SELECT COUNT(*) FROM event_types", default=0),
        "tickets": db.scalar(conn, "SELECT COUNT(*) FROM tickets", default=0),
        "tickets_linked": db.scalar(conn, "SELECT COUNT(DISTINCT ticket_id) FROM ticket_links", default=0),
        "links": {r["kind"]: r["n"] for r in db.rows(conn, "SELECT kind, COUNT(*) n FROM ticket_links GROUP BY kind")},
    }
