"""Import jobs: staged on upload, executed one at a time by a background worker thread.

Jobs and their files are persisted, so a restart marks running jobs "interrupted" and they can be re-run.
Imports are idempotent upserts, so re-running a job never duplicates data.
"""
from __future__ import annotations

import queue
import re
import threading
import time
import traceback
import uuid
from pathlib import Path

from ... import db
from ...bus import bus
from ...config import cfg
from . import events as event_import
from . import mapping, readers, sync
from . import tickets as ticket_import


class Cancelled(Exception):
    pass


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)[:120] or "upload.csv"


def job_view(row: dict | None) -> dict | None:
    if not row:
        return None
    out = dict(row)
    for key in ("preview", "mapping", "options", "stats"):
        out[key] = db.loads(out.get(key), {})
    out.pop("stored_path", None)
    return out


class Runner:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._cancel: set[str] = set()
        self._thread: threading.Thread | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        with db.session() as conn:
            conn.execute("UPDATE jobs SET status='interrupted', message='Server restarted while this import was running. Run it again to finish.' "
                         "WHERE status='running'")
            queued = [r["id"] for r in db.rows(conn, "SELECT id FROM jobs WHERE status='queued' ORDER BY created_at")]
        for job_id in queued:
            self._queue.put(job_id)
        self._thread = threading.Thread(target=self._loop, name="nocturne-import", daemon=True)
        self._thread.start()

    # ── staging ───────────────────────────────────────────────────────────────
    def stage(self, conn, filename: str, content: bytes, user: dict) -> dict:
        job_id = uuid.uuid4().hex[:12]
        path = Path(cfg.storage.uploads) / f"{job_id}__{_safe_name(filename)}"
        path.write_bytes(content)
        try:
            headers, sample_rows, meta = readers.sample(path)
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise ValueError(f"Could not read {filename}: {exc}") from exc
        proposal = mapping.propose(headers, sample_rows)
        preview = {"headers": headers, "rows": [r + [""] * (len(headers) - len(r)) for r in sample_rows[:8]],
                   "meta": meta, "proposal": proposal}
        conn.execute(
            "INSERT INTO jobs(id, dataset, filename, stored_path, size_bytes, status, stage, message, preview, mapping, "
            "created_by, created_at) VALUES (?,?,?,?,?, 'staged', 'Awaiting review', ?, ?, ?, ?, ?)",
            (job_id, proposal["dataset"], filename, str(path), len(content),
             "Review the column mapping, then start the import.", db.dumps(preview),
             db.dumps({f: m["col"] for f, m in proposal["mapping"].items()}), user["username"], db.now()))
        return job_view(db.one(conn, "SELECT * FROM jobs WHERE id=?", (job_id,)))

    def submit(self, conn, job_id: str, dataset: str, field_map: dict, options: dict) -> dict:
        job = db.one(conn, "SELECT * FROM jobs WHERE id=?", (job_id,))
        if not job:
            raise LookupError("Import not found.")
        if job["status"] in ("queued", "running"):
            raise ValueError("This import is already running.")
        if dataset not in ("events", "tickets"):
            raise ValueError("Choose whether the file holds events or tickets.")
        clean_map = {f: int(c) for f, c in field_map.items() if c not in (None, "", -1, "-1")}
        missing = mapping.missing_required(dataset, clean_map)
        if missing:
            raise ValueError("Map these fields before importing: " + "; ".join(missing))
        options = options or {}
        conn.execute("UPDATE jobs SET dataset=?, mapping=?, options=?, status='queued', progress=0, stage='Queued', "
                     "message='Waiting for the import worker', stats=NULL, started_at=NULL, finished_at=NULL WHERE id=?",
                     (dataset, db.dumps(clean_map), db.dumps(options or {}), job_id))
        conn.execute("DELETE FROM job_rejects WHERE job_id=?", (job_id,))
        conn.commit()
        self._cancel.discard(job_id)  # a cancel aimed at an earlier run must not stop this one
        self._queue.put(job_id)
        return job_view(db.one(conn, "SELECT * FROM jobs WHERE id=?", (job_id,)))

    def cancel(self, job_id: str) -> None:
        self._cancel.add(job_id)

    # ── execution ─────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process(job_id)
            except Exception:  # never let the worker die
                traceback.print_exc()

    def _process(self, job_id: str) -> None:
        conn = db.connect()
        try:
            job = db.one(conn, "SELECT * FROM jobs WHERE id=?", (job_id,))
            if not job or job["status"] != "queued":
                return
            if job_id in self._cancel:
                self._finish(conn, job_id, "cancelled", "Cancelled before it started.", {})
                return
            conn.execute("UPDATE jobs SET status='running', started_at=?, stage='Starting' WHERE id=?", (db.now(), job_id))
            conn.commit()
            last = {"t": 0.0}

            def report(progress: float, stage: str, message: str = "") -> None:
                if job_id in self._cancel:
                    raise Cancelled()
                if time.time() - last["t"] < 0.35 and progress < 0.999:
                    return
                last["t"] = time.time()
                conn.execute("UPDATE jobs SET progress=?, stage=?, message=? WHERE id=?",
                             (round(progress, 4), stage, message, job_id))
                conn.commit()
                bus.publish("job", {"id": job_id, "status": "running", "progress": progress, "stage": stage, "message": message})

            started = time.time()
            table = readers.open_table(job["stored_path"])
            field_map = db.loads(job["mapping"], {})
            options = db.loads(job["options"], {})
            importer = event_import if job["dataset"] == "events" else ticket_import
            result = importer.run(conn, job, table, field_map, options, report)
            conn.commit()

            synced = sync.resync(conn, lambda p, msg: report(0.93 + 0.06 * p, "Syncing", msg))
            result["linking"] = synced.pop("linking")
            result["sync"] = synced
            rejects = result.pop("rejects", [])
            conn.executemany("INSERT INTO job_rejects(job_id, row_no, reason, raw) VALUES (?,?,?,?)",
                             [(job_id, *r) for r in rejects[: cfg.etl.max_rejects_kept]])
            result["reject_reasons"] = {}
            for _, reason, _ in rejects:
                result["reject_reasons"][reason] = result["reject_reasons"].get(reason, 0) + 1
            result["seconds"] = round(time.time() - started, 1)
            result["file"] = table.meta
            summary = _summary(job["dataset"], result["stats"])
            self._finish(conn, job_id, "succeeded", summary, result)
            db.audit(conn, {"username": job["created_by"]}, "data.import", job["filename"], summary)
            conn.commit()
            bus.publish("data", {"reason": "import", "job": job_id})
        except Cancelled:
            conn.rollback()
            try:  # batches committed before the cancel are kept, so bring counters, links and search up to date with them
                sync.resync(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                traceback.print_exc()
            self._finish(conn, job_id, "cancelled", "Cancelled. Records written before the cancel are kept; re-run to complete.", {})
            bus.publish("data", {"reason": "import", "job": job_id})
        except Exception as exc:
            conn.rollback()
            traceback.print_exc()
            self._finish(conn, job_id, "failed", str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}", {})
        finally:
            self._cancel.discard(job_id)
            conn.close()

    def _finish(self, conn, job_id: str, status: str, message: str, stats: dict) -> None:
        conn.execute("UPDATE jobs SET status=?, message=?, stats=?, progress=COALESCE(?, progress), stage=?, finished_at=? WHERE id=?",
                     (status, message, db.dumps(stats), 1.0 if status == "succeeded" else None,
                      {"succeeded": "Complete", "failed": "Failed", "cancelled": "Cancelled"}.get(status, status),
                      db.now(), job_id))
        conn.commit()
        bus.publish("job", {"id": job_id, "status": status, "progress": 1.0, "message": message})


def _summary(dataset: str, s: dict) -> str:
    k = "events" if dataset == "events" else "tickets"
    parts = [f"{s.get(f'{k}_inserted', 0):,} new", f"{s.get(f'{k}_updated', 0):,} updated"]
    if s.get(f"{k}_unchanged"):
        parts.append(f"{s[f'{k}_unchanged']:,} unchanged")
    if s.get("tickets_skipped_older"):
        parts.append(f"{s['tickets_skipped_older']:,} skipped as older than stored")
    if s.get("tickets_skipped_unversioned"):
        parts.append(f"{s['tickets_skipped_unversioned']:,} skipped (no updated time; stored version kept)")
    if s.get("duplicates_in_file"):
        parts.append(f"{s['duplicates_in_file']:,} duplicate rows")
    parts.append(f"{s.get('rejected', 0):,} rejected")
    return f"{s.get(f'{k}_in_file', 0):,} {k} in file: " + ", ".join(parts)


runner = Runner()
