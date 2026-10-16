"""Ticket import: parse → normalise dates/states → extract sites, IPs, devices → upsert."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from ... import db
from ...config import cfg
from .. import classify as C
from .. import textmine as T
from . import timeparse as TP

_CLOSED = {s.lower() for s in cfg.etl.closed_states}
_KIND = re.compile(r"^[A-Za-z]+")


def _text(value) -> str | None:
    v = C.clean(value)
    return v.replace("\r\n", "\n").replace("\r", "\n").strip() if v else None


def _stamp(raw, day_first: bool) -> str | None:
    d, secs = TP.parse_moment(C.clean(raw), day_first)
    return TP.iso(d, secs)[:19] if d else None


def run(conn, job: dict, table, mapping: dict[str, int], options: dict, report) -> dict:
    get = {f: i for f, i in mapping.items() if i is not None}
    width = len(table.headers)
    extra_cols = [i for i in range(width) if i not in get.values()]
    stats, rejects, coverage = Counter(), [], Counter()

    def val(row, field):
        i = get.get(field)
        return row[i] if i is not None and i < len(row) else None

    report(0.03, "Reading rows", "Parsing tickets")
    raw_rows = list(table.rows())
    date_samples = [val(r, f) or "" for _, r in raw_rows for f in ("created_at", "closed_at")]
    order = TP.detect_order(date_samples, "tickets")
    day_first = order["day_first"]
    unreadable = Counter()

    known_devices = {r["name_key"]: r["id"] for r in db.rows(conn, "SELECT id, name_key FROM devices")}
    records, seen = [], set()
    for n, (row_no, row) in enumerate(raw_rows):
        stats["rows_read"] += 1
        number = C.clean(val(row, "number"))
        if not number:
            stats["rejected"] += 1
            rejects.append((row_no, "Missing ticket number", ",".join(row)[:500]))
            continue
        number = number.upper()
        if number in seen:
            stats["duplicates_in_file"] += 1
        seen.add(number)
        state = C.clean(val(row, "state"))
        is_open = 0 if (state or "").lower() in _CLOSED else 1
        created, updated, closed = (_stamp(val(row, f), day_first) for f in ("created_at", "updated_at", "closed_at"))
        for f, got in (("created_at", created), ("closed_at", closed)):
            if got is None and not C.is_null(val(row, f)):
                unreadable[f] += 1
        if closed and not state:
            is_open = 0
        found = T.devices_in_text("\n".join(x for x in (_text(val(row, "short_description")), _text(val(row, "description")),
                                                          _text(val(row, "work_notes")), C.clean(val(row, "cmdb_ci"))) if x), known_devices)
        start_raw = T.stated_start(f"{_text(val(row, 'short_description')) or ''}\n{_text(val(row, 'description')) or ''}")
        incident_start = None
        if start_raw:
            stated = _stamp(start_raw, day_first) if created else None
            if stated and _plausible_start(stated, created):
                incident_start = stated
                stats["stated_start_times_used"] += 1
            else:
                stats["stated_start_times_ignored"] += 1
        minutes = None
        if created and closed:
            delta = datetime.fromisoformat(closed) - datetime.fromisoformat(created)
            minutes = max(int(delta.total_seconds() // 60), 0)
        short, desc = _text(val(row, "short_description")), _text(val(row, "description"))
        notes, close_notes, ci = _text(val(row, "work_notes")), _text(val(row, "close_notes")), C.clean(val(row, "cmdb_ci"))
        blob = "\n".join(x for x in (short, desc, notes, close_notes, ci) if x)
        sites = T.sites_in_text(blob)
        ips = T.ips_in_text(blob)
        devices = sorted(found) if found else sorted(T.devices_in_text(blob, known_devices))
        extra = {table.headers[i]: row[i].strip() for i in extra_cols if i < len(row) and not C.is_null(row[i])}
        rec = (number, _KIND.match(number).group(0) if _KIND.match(number) else None, state, is_open,
               C.clean(val(row, "priority")), C.clean(val(row, "category")), C.clean(val(row, "opened_by")),
               C.clean(val(row, "assigned_to")), C.clean(val(row, "assignment_group")), created, updated, closed, minutes, incident_start,
               short, desc, notes, _text(val(row, "work_notes_list")), close_notes, ci,
               T.resolution_summary(close_notes, notes, bool(is_open)),
               db.dumps(sites), db.dumps(ips), db.dumps(devices), job["id"], db.dumps(extra))
        records.append(rec)
        coverage["created_at"] += created is not None
        coverage["closed_at"] += closed is not None
        coverage["assigned_to"] += rec[7] is not None
        coverage["opened_by"] += rec[6] is not None
        coverage["work_notes"] += notes is not None
        coverage["mentions_site"] += bool(sites)
        coverage["mentions_ip"] += bool(ips)
        coverage["mentions_device"] += bool(devices)
        if n % 500 == 0:
            report(0.05 + 0.5 * (n + 1) / max(len(raw_rows), 1), "Extracting facts", f"{n + 1:,} tickets parsed")

    report(0.6, "Writing tickets", f"{len(records):,} tickets")
    write, outcome, transitions, records = _reconcile(conn, records)
    stats.update(outcome)
    conn.executemany(
        f"""INSERT INTO tickets({", ".join(COLUMNS)})
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(number) DO UPDATE SET kind=excluded.kind, state=excluded.state, is_open=excluded.is_open,
               priority=excluded.priority, category=excluded.category, opened_by=excluded.opened_by,
               assigned_to=excluded.assigned_to, assignment_group=excluded.assignment_group, created_at=excluded.created_at,
               updated_at=excluded.updated_at, closed_at=excluded.closed_at, resolve_minutes=excluded.resolve_minutes,
               incident_start=excluded.incident_start,
               short_description=excluded.short_description, description=excluded.description,
               work_notes=excluded.work_notes, work_notes_list=excluded.work_notes_list, close_notes=excluded.close_notes,
               cmdb_ci=excluded.cmdb_ci, resolution=excluded.resolution, sites=excluded.sites, ips=excluded.ips,
               devices=excluded.devices, job_id=excluded.job_id, extra=excluded.extra""",
        write)
    total = max(len(records), 1)
    stats["tickets_in_file"] = len(seen)
    return {
        "stats": dict(stats), "rejects": rejects,
        "dates": {"format": order["order"], "evidence": order["evidence"],
                  "with_open_date": sum(1 for r in records if r[9]), "without_open_date": sum(1 for r in records if not r[9]),
                  "first": min((r[9] for r in records if r[9]), default=None), "last": max((r[9] for r in records if r[9]), default=None),
                  **{f"unreadable_{k}": v for k, v in unreadable.items()}},
        "coverage": {k: round(100 * v / total, 1) for k, v in coverage.items()},
        "kinds": dict(Counter(r[1] for r in records)),
        "states": dict(Counter(r[2] or "—" for r in records)),
        "state_changes": dict(transitions),
    }


COLUMNS = ("number", "kind", "state", "is_open", "priority", "category", "opened_by", "assigned_to", "assignment_group",
           "created_at", "updated_at", "closed_at", "resolve_minutes", "incident_start", "short_description", "description", "work_notes",
           "work_notes_list", "close_notes", "cmdb_ci", "resolution", "sites", "ips", "devices", "job_id", "extra")
_COMPARED = [i for i, c in enumerate(COLUMNS) if c != "job_id"]
_UPDATED_AT = COLUMNS.index("updated_at")


def _plausible_start(stated: str, created: str) -> bool:
    """A stated start counts only if it sits just before the ticket opened (typos and other time zones fall outside)."""
    gap = (datetime.fromisoformat(created) - datetime.fromisoformat(stated)).total_seconds() / 3600
    return -cfg.etl.stated_start_max_minutes_after / 60 <= gap <= cfg.etl.stated_start_max_hours_before


def _reconcile(conn, records: list[tuple]) -> tuple[list[tuple], dict, Counter, list[tuple]]:
    """Keep one current version per ticket and decide what actually needs writing.

    In the file, the most recently updated row of a ticket wins (file order breaks ties). Against the database,
    a version older than the stored one is skipped, so uploading an old export never reopens a closed ticket
    (a row without an updated time never replaces a stored ticket that has one);
    identical versions are skipped; everything else is inserted or updated, and status changes are counted.
    """
    latest: dict[str, tuple] = {}
    for rec in records:
        cur = latest.get(rec[0])
        if cur is None or (rec[_UPDATED_AT] or "") >= (cur[_UPDATED_AT] or ""):
            latest[rec[0]] = rec
    numbers = list(latest)
    stored: dict[str, dict] = {}
    for i in range(0, len(numbers), 900):
        chunk = numbers[i:i + 900]
        stored.update({r["number"]: r for r in db.rows(conn, f"SELECT {', '.join(COLUMNS)} FROM tickets "
                                                             f"WHERE number IN ({','.join('?' * len(chunk))})", chunk)})
    write, transitions = [], Counter()
    outcome = Counter({"tickets_inserted": 0, "tickets_updated": 0, "tickets_unchanged": 0})
    for number, rec in latest.items():
        old = stored.get(number)
        if old is None:
            outcome["tickets_inserted"] += 1
            write.append(rec)
            continue
        if old["updated_at"] and rec[_UPDATED_AT] and rec[_UPDATED_AT] < old["updated_at"]:
            outcome["tickets_skipped_older"] += 1
            continue
        if old["updated_at"] and not rec[_UPDATED_AT]:
            # The stored ticket carries a version and this row does not, so it cannot be shown to be newer:
            # keep the stored one rather than risk reopening a closed ticket from an unversioned export.
            outcome["tickets_skipped_unversioned"] += 1
            continue
        if all(old[COLUMNS[i]] == rec[i] for i in _COMPARED):
            outcome["tickets_unchanged"] += 1
            continue
        outcome["tickets_updated"] += 1
        if (old["state"] or "") != (rec[2] or ""):
            transitions[f"{old['state'] or '—'} → {rec[2] or '—'}"] += 1
        write.append(rec)
    return write, dict(outcome), transitions, list(latest.values())
