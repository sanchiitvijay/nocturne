"""Event import: parse and check timestamps → resolve devices & sites → classify → upsert."""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime

from ... import db
from ...config import cfg
from .. import classify as C
from .. import textmine as T
from . import timeparse as TP


def _int(value) -> int | None:
    v = C.clean(value)
    if v is None:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _hash_id(*parts) -> int:
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:13], 16)


def type_overrides(conn) -> dict[int, dict]:
    return {r["type_id"]: r for r in db.rows(conn, "SELECT type_id, name, severity, category FROM event_types "
                                                     "WHERE severity IS NOT NULL OR category IS NOT NULL OR name IS NOT NULL")}


def run(conn, job: dict, table, mapping: dict[str, int], options: dict, report) -> dict:
    """Import one events file. `report(progress, stage, message)` updates the job."""
    get = {f: i for f, i in mapping.items() if i is not None}
    width = len(table.headers)
    extra_cols = [i for i in range(width) if i not in get.values()]
    stats = Counter()
    rejects: list[tuple] = []
    recs: list[dict] = []
    coverage = Counter()

    def val(row, field):
        i = get.get(field)
        return row[i] if i is not None and i < len(row) else None

    if get.get("time") is None and get.get("date") is None:
        raise ValueError("No event timestamp column is mapped. Map the event time (date and time) before importing.")

    def raw_time(row):
        parts = [val(row, "date"), val(row, "time")] if get.get("date") is not None else [val(row, "time")]
        return " ".join(p.strip() for p in parts if p and p.strip()) or None

    report(0.02, "Reading rows", "Checking timestamps")
    sample = [raw_time(r) or "" for _, r in table.rows()]
    order = TP.detect_order(sample)
    filled = [v for v in sample if v][:5000]
    if filled and sum(TP.time_only(v) for v in filled) > 0.5 * len(filled):
        raise ValueError("The mapped event time holds times without dates. Every event needs a full date and time: "
                         "map the timestamp column (or add the date column) and run the import again.")
    now = datetime.now()
    seen_ids: set[int] = set()
    report(0.04, "Reading rows", "Parsing the file")
    for n, (row_no, row) in enumerate(table.rows()):
        stats["rows_read"] += 1
        raw = raw_time(row)
        day_first = order["day_first"]
        if order["mixed"]:
            evident = TP.self_evident(raw)
            if evident is None and raw and not TP._ISO_DATE.search(raw):
                stats["rejected"] += 1
                rejects.append((row_no, "Ambiguous date (could be DD-MM or MM-DD)", ",".join(row)[:500]))
                continue
            day_first = evident if evident is not None else day_first
        d, tod = TP.parse_moment(raw, day_first)
        problem = TP.check(d, tod, raw, now) or (None if tod is not None else "Date without a time")
        if problem:
            stats["rejected"] += 1
            rejects.append((row_no, f"{problem}: {raw}" if raw else problem, ",".join(row)[:500]))
            continue
        type_id = _int(val(row, "type_id"))
        source_name = C.clean(val(row, "type_name"))
        message = C.clean(val(row, "message"))
        device = C.clean(val(row, "device_name"))
        ip = T.valid_ip(C.clean(val(row, "ip")))
        location = val(row, "location")
        if location and "\n" in location:
            stats["repaired_multiline_fields"] += 1
        sid = _int(val(row, "source_id")) if "source_id" in get else None
        if sid is None and "source_id" not in get:
            sid = _hash_id(raw, device, ip, type_id, message)
        if sid is None:
            stats["rejected"] += 1
            rejects.append((row_no, "Missing or non-numeric event ID", ",".join(row)[:500]))
            continue
        if not message and not source_name and type_id is None:
            stats["rejected"] += 1
            rejects.append((row_no, "Row has no event type and no event text", ",".join(row)[:500]))
            continue
        if sid in seen_ids:
            stats["duplicates_in_file"] += 1
            continue
        seen_ids.add(sid)
        if device is None and ip:
            device = ip
        extra = {table.headers[i] if i < width else f"column_{i + 1}": row[i].strip()
                 for i in extra_cols if i < len(row) and not C.is_null(row[i])}
        extra.update({f"column_{i + 1}": row[i].strip() for i in range(width, len(row)) if not C.is_null(row[i])})
        rec = {
            "row": row_no, "sid": sid, "ts": TP.iso(d, tod), "type_id": type_id, "source_name": source_name,
            "message": message, "device": device, "ip": ip, "node_id": _int(val(row, "node_id")),
            "machine_type": C.clean(val(row, "machine_type")), "vendor": C.clean(val(row, "vendor")),
            "status": _int(val(row, "status_code")), "location": T.clean_location(C.clean(location)),
            "site_hint": T.site_code(C.clean(val(row, "site_hint"))), "severity_src": C.clean(val(row, "severity")),
            "extra": extra or None,
        }
        for field in ("device", "ip", "message", "type_id", "status", "location", "machine_type"):
            coverage[field] += rec[field] is not None
        recs.append(rec)
        if n % 4000 == 0:
            report(0.02 + 0.33 * table.progress(), "Reading rows", f"{stats['rows_read']:,} rows read")

    if not recs:
        return {"stats": dict(stats), "rejects": rejects, "dates": {}, "coverage": {}}

    stamps = sorted(r["ts"] for r in recs)
    days = len({t[:10] for t in stamps})
    dates_info = {"source": "timestamps in the file", "format": order["order"], "evidence": order["evidence"],
                  "precision": TP.precision(sample[:5000]), "first": stamps[0][:16], "last": stamps[-1][:16], "days_covered": days}

    # ── devices, sites, types ─────────────────────────────────────────────────
    report(0.42, "Resolving devices", "Building device and site registry")
    overrides = type_overrides(conn)
    device_ids, site_info = _upsert_inventory(conn, recs, stats)
    _upsert_types(conn, recs)
    trust_hint = site_info["__summary__"]["site_column_trusted"]

    # ── events ───────────────────────────────────────────────────────────────
    existing = set()
    sids = [r["sid"] for r in recs]
    for i in range(0, len(sids), 30000):
        chunk = sids[i:i + 30000]
        q = f"SELECT source_id FROM events WHERE source='import' AND source_id IN ({','.join('?' * len(chunk))})"
        existing.update(x[0] for x in conn.execute(q, chunk))
    created = db.now()
    sql = """INSERT INTO events(source, source_id, ts, type_id, name, message, device_id, device_name,
                 ip, site_code, status_code, severity, category, actionable, transition, pair_key, job_id, created_at, extra)
             VALUES ('import',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
             ON CONFLICT(source, source_id) DO UPDATE SET ts=excluded.ts,
                 type_id=excluded.type_id, name=excluded.name, message=excluded.message, device_id=excluded.device_id,
                 device_name=excluded.device_name, ip=excluded.ip, site_code=excluded.site_code,
                 status_code=excluded.status_code, severity=excluded.severity, category=excluded.category,
                 actionable=excluded.actionable, transition=excluded.transition, pair_key=excluded.pair_key,
                 job_id=excluded.job_id, extra=excluded.extra
             WHERE events.ts IS NOT excluded.ts OR events.type_id IS NOT excluded.type_id OR events.name IS NOT excluded.name
                OR events.message IS NOT excluded.message OR events.device_id IS NOT excluded.device_id
                OR events.device_name IS NOT excluded.device_name OR events.ip IS NOT excluded.ip
                OR events.site_code IS NOT excluded.site_code OR events.status_code IS NOT excluded.status_code
                OR events.severity IS NOT excluded.severity OR events.category IS NOT excluded.category
                OR events.extra IS NOT excluded.extra"""
    # Events never change at the source: identical re-uploads are skipped, corrected rows are updated,
    # and the analyst's working state (new / acknowledged / resolved) is never touched.
    batch, total = [], len(recs)
    sev_counter, seen_in_file = Counter(), set()
    written = 0
    for i, r in enumerate(recs):
        seen_in_file.add(r["sid"])
        name = C.event_name(r["type_id"], r["source_name"], overrides)
        key = r["device"].lower() if r["device"] else None
        message = r["message"] or name
        if r["device"]:
            message = message.replace("[DEVICE_ID]", r["device"]).replace("[HOSTNAME]", r["device"])
        message = T.strip_markup(message)
        cls = C.classify(r["type_id"], name, message, overrides)
        if r["severity_src"] and r["severity_src"].upper() in C.SEVERITIES:
            cls["severity"] = r["severity_src"].upper()
        sev_counter[cls["severity"]] += 1
        site = site_info.get(key) or (r["site_hint"] if trust_hint else None)
        batch.append((r["sid"], r["ts"], r["type_id"], name, message, device_ids.get(key), r["device"],
                      r["ip"], site, r["status"], cls["severity"], cls["category"], cls["actionable"],
                      cls["transition"], C.pair_key(key, name, message), job["id"], created, db.dumps(r["extra"])))
        if len(batch) >= cfg.etl.batch_size or i == total - 1:
            written += max(conn.executemany(sql, batch).rowcount, 0)
            conn.commit()
            batch = []
            report(0.45 + 0.45 * (i + 1) / total, "Writing events", f"{i + 1:,} of {total:,} events written")

    stats["events_inserted"] = len(seen_in_file - existing)
    stats["events_updated"] = max(written - stats["events_inserted"], 0)
    stats["events_unchanged"] = len(seen_in_file & existing) - stats["events_updated"]
    stats["events_in_file"] = len(recs)

    cov = {k: round(100 * v / len(recs), 1) for k, v in coverage.items()}
    cov["site"] = round(100 * sum(1 for r in recs if (site_info.get((r["device"] or "").lower()) or (trust_hint and r["site_hint"]))) / len(recs), 1)
    return {"stats": dict(stats), "rejects": rejects, "dates": dates_info, "coverage": cov,
            "severity": dict(sev_counter), "sites": site_info.get("__summary__", {})}


def _upsert_inventory(conn, recs: list[dict], stats: Counter) -> tuple[dict, dict]:
    agg: dict[str, dict] = {}
    labels: dict[str, Counter] = defaultdict(Counter)
    addresses: dict[str, Counter] = defaultdict(Counter)
    hint_agree = hint_total = 0
    for r in sorted(recs, key=lambda x: (x["ts"], x["sid"])):
        if not r["device"]:
            continue
        key = r["device"].lower()
        a = agg.setdefault(key, {"name": r["device"], "ip": None, "node_id": None, "machine_type": None, "vendor": None,
                                 "location": None, "status": None, "site": None, "hints": Counter(), "latest": None})
        a["latest"] = r["ts"]  # rows are walked oldest first, so this ends as the device's newest event in the file
        for f_src, f_dst in (("ip", "ip"), ("node_id", "node_id"), ("machine_type", "machine_type"),
                             ("vendor", "vendor"), ("location", "location"), ("status", "status")):
            if r[f_src] is not None and not (f_src == "node_id" and r[f_src] == 0):
                a[f_dst] = r[f_src]
        if r["site_hint"]:
            a["hints"][r["site_hint"]] += 1
    site_of: dict[str, str] = {}
    for a in agg.values():
        a["site"] = T.site_from_device(a["name"])
        a["hint"] = a["hints"].most_common(1)[0][0] if a["hints"] else None
        if a["site"] and a["hint"]:
            hint_total += 1
            hint_agree += a["site"] == a["hint"]
    # The site column is only trusted as a fallback when it agrees with device names often enough.
    agreement = 100 * hint_agree / hint_total if hint_total else 100.0
    trust_hint = agreement >= cfg.etl.site_column_min_agreement
    for key, a in agg.items():
        site = a["site"] or (a["hint"] if trust_hint else None)
        a["site"] = site
        if site:
            site_of[key] = site
            lbl = T.site_label_from_device(a["name"]) or T.site_label_from_location(a["location"])
            if lbl:
                labels[site][lbl] += 1
            if a["location"]:
                addresses[site][a["location"]] += 1
        a["role"] = C.device_role(f"{a['name']} {a['machine_type'] or ''} {a['vendor'] or ''}")

    known = {r["name_key"]: r for r in db.rows(conn, "SELECT id, name_key, last_seen FROM devices")}
    existing = {k: r["id"] for k, r in known.items()}
    # A file newer than what is stored refreshes device attributes; an older file (uploaded late) only fills gaps,
    # so upload order never rolls a device back to a stale IP, status or location.
    newer, older = [], []
    for k, a in agg.items():
        row = (a["name"], k, a["ip"], a["node_id"], a["site"], a["role"], a["machine_type"], a["vendor"], a["location"], a["status"])
        last = (known.get(k) or {}).get("last_seen")
        (older if last and a["latest"] and a["latest"] < last else newer).append(row)
    insert = """INSERT INTO devices(name, name_key, ip, node_id, site_code, role, machine_type, vendor, location, last_status)
                VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(name_key) DO UPDATE SET """
    conn.executemany(insert + """name=excluded.name, ip=COALESCE(excluded.ip, ip),
             node_id=COALESCE(excluded.node_id, node_id), site_code=COALESCE(excluded.site_code, site_code),
             role=excluded.role, machine_type=COALESCE(excluded.machine_type, machine_type),
             vendor=COALESCE(excluded.vendor, vendor), location=COALESCE(excluded.location, location),
             last_status=COALESCE(excluded.last_status, last_status)""", newer)
    conn.executemany(insert + """ip=COALESCE(ip, excluded.ip), node_id=COALESCE(node_id, excluded.node_id),
             site_code=COALESCE(site_code, excluded.site_code), machine_type=COALESCE(machine_type, excluded.machine_type),
             vendor=COALESCE(vendor, excluded.vendor), location=COALESCE(location, excluded.location),
             last_status=COALESCE(last_status, excluded.last_status)""", older)
    if older:
        stats["devices_from_older_file"] = len(older)
    ids = {r["name_key"]: r["id"] for r in db.rows(conn, "SELECT id, name_key FROM devices")}
    stats["devices_new"] = len(set(agg) - set(existing))
    stats["devices_updated"] = len(set(agg) & set(existing))

    now = db.now()
    site_rows = []
    for site in {s for s in site_of.values()}:
        lbl = labels[site].most_common(1)[0][0] if labels[site] else None
        addr = addresses[site].most_common(1)[0][0] if addresses[site] else None
        site_rows.append((site, f"{lbl[0]}, {lbl[1]}" if lbl else None, lbl[0] if lbl else None, lbl[1] if lbl else None, addr, now))
    conn.executemany(
        """INSERT INTO sites(code, label, city, state, address, updated_at) VALUES (?,?,?,?,?,?)
           ON CONFLICT(code) DO UPDATE SET label=COALESCE(excluded.label, label), city=COALESCE(excluded.city, city),
             state=COALESCE(excluded.state, state), address=COALESCE(excluded.address, address), updated_at=excluded.updated_at""",
        site_rows)
    stats["sites_seen"] = len(site_rows)
    site_of["__summary__"] = {"site_column_agreement_pct": round(agreement, 1) if hint_total else None,
                              "devices_compared": hint_total, "site_column_trusted": trust_hint}
    return ids, site_of


def _upsert_types(conn, recs: list[dict]) -> None:
    names: dict[int, Counter] = defaultdict(Counter)
    samples: dict[int, str] = {}
    for r in recs:
        if r["type_id"] is None:
            continue
        if r["source_name"]:
            names[r["type_id"]][r["source_name"]] += 1
        if r["message"] and r["type_id"] not in samples:
            text = r["message"]
            if r["device"]:
                text = text.replace("[DEVICE_ID]", r["device"]).replace("[HOSTNAME]", r["device"])
            samples[r["type_id"]] = T.strip_markup(text)[:300]
    now = db.now()
    conn.executemany(
        """INSERT INTO event_types(type_id, source_name, sample, updated_at) VALUES (?,?,?,?)
           ON CONFLICT(type_id) DO UPDATE SET source_name=COALESCE(excluded.source_name, source_name),
             sample=COALESCE(sample, excluded.sample), updated_at=excluded.updated_at""",
        [(t, names[t].most_common(1)[0][0] if names[t] else None, samples.get(t), now)
         for t in set(names) | set(samples)])
