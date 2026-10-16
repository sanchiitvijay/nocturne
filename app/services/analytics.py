"""Dashboard metrics. Windows are relative to the newest event ("as of"), so historical exports read naturally."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from .. import db
from ..cache import cache
from ..config import cfg
from . import correlate as K

WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "all": None}


def _stamp(value: str, label: str, end_of_day: bool = False) -> str:
    """Normalise a user-supplied window bound; raises ValueError with a readable message."""
    try:
        text = value.strip().replace("T", " ")
        moment = datetime.fromisoformat(text)
        if end_of_day and len(text) == 10:  # a bare end date includes that whole day
            moment += timedelta(days=1, seconds=-1)
        return moment.strftime(K.FMT)
    except (AttributeError, ValueError):
        raise ValueError(f"{label} must be a date or date and time such as 2026-05-19 or 2026-05-19 20:00.") from None


def resolve_window(conn, window: str, start: str | None = None, end: str | None = None) -> dict:
    newest = K.as_of(conn)
    if window == "custom" and start:
        start = _stamp(start, "The window start")
        end = _stamp(end, "The window end", end_of_day=True) if end else newest
        if end and start > end:
            raise ValueError("The window start must come before its end.")
        return {"window": "custom", "start": start, "end": end, "as_of": newest}
    span = WINDOWS.get(window, WINDOWS["7d"])
    if not newest or span is None:
        return {"window": "all" if span is None else window, "start": None, "end": newest, "as_of": newest}
    end_dt = datetime.fromisoformat(newest)
    return {"window": window, "start": (end_dt - span).strftime(K.FMT), "end": newest, "as_of": newest}


def _where(w: dict, alias: str = "") -> tuple[str, list]:
    p = f"{alias}." if alias else ""
    clauses, params = [f"{p}ts IS NOT NULL"], []
    if w.get("start"):
        clauses.append(f"{p}ts >= ?")
        params.append(w["start"])
    if w.get("end"):
        clauses.append(f"{p}ts <= ?")
        params.append(w["end"])
    return " AND ".join(clauses), params


def _previous(w: dict) -> dict | None:
    if not w.get("start") or not w.get("end"):
        return None
    s, e = datetime.fromisoformat(w["start"]), datetime.fromisoformat(w["end"])
    return {"start": (s - (e - s)).strftime(K.FMT), "end": w["start"]}


def _kpi_counts(conn, w: dict) -> dict:
    where, params = _where(w)
    r = db.one(conn, f"""SELECT COUNT(*) total, SUM(actionable) actionable,
                             SUM(CASE WHEN actionable=1 AND state<>'resolved' THEN 1 ELSE 0 END) open_alerts,
                             SUM(CASE WHEN severity='P1' AND actionable=1 THEN 1 ELSE 0 END) p1,
                             COUNT(DISTINCT CASE WHEN actionable=1 THEN device_id END) devices,
                             COUNT(DISTINCT CASE WHEN actionable=1 THEN site_code END) sites
                         FROM events WHERE {where}""", params)
    return {k: (v or 0) for k, v in r.items()}


def overview(conn, window: str = "7d", start: str | None = None, end: str | None = None) -> dict:
    w = resolve_window(conn, window, start, end)
    return cache.get(conn, "overview", (w["window"], w["start"], w["end"]), lambda: _overview(conn, w))


def _overview(conn, w: dict) -> dict:
    where, params = _where(w)
    prev_w = _previous(w)
    prev_k = _kpi_counts(conn, prev_w) if prev_w else None
    outs = K.outages(conn, w["start"], w["end"])
    osum = K.outage_summary(outs)

    # One scan of the window, grouped at the finest grain the dashboard needs (hour × severity × category ×
    # actionable × state × source × type). Every count, mix and series below is rolled up from it in Python,
    # instead of scanning the window once per chart.
    rollup = conn.execute(f"""SELECT strftime('%Y-%m-%d %H', ts) hb, severity, category, actionable, state, source, type_id, name,
                                     COUNT(*) n FROM events WHERE {where} GROUP BY 1, 2, 3, 4, 5, 6, 7, 8""", params).fetchall()
    # A second scan of the actionable alerts by device × site feeds the device and site rankings, the US map and the
    # distinct device/site counts.
    places = conn.execute(f"""SELECT device_id, site_code, COUNT(*) n, SUM(CASE WHEN severity='P1' THEN 1 ELSE 0 END) p1
                              FROM events WHERE {where} AND actionable=1 GROUP BY device_id, site_code""", params).fetchall()
    now_k = {"total": 0, "actionable": 0, "open_alerts": 0, "p1": 0,
             "devices": len({r[0] for r in places if r[0] is not None}), "sites": len({r[1] for r in places if r[1] is not None})}

    span_hours = None
    if w["start"] and w["end"]:
        span_hours = (datetime.fromisoformat(w["end"]) - datetime.fromisoformat(w["start"])).total_seconds() / 3600
    hourly = bool(span_hours and span_hours <= 24 * 8)
    series = defaultdict(lambda: {"P1": 0, "P2": 0, "P3": 0, "P4": 0})   # volume over time, stacked by severity
    score = defaultdict(lambda: defaultdict(int))                         # the night's score: hour of day × category
    worst: dict[tuple, str] = {}
    severity, states, sources = defaultdict(int), defaultdict(int), defaultdict(int)
    cats: dict = defaultdict(lambda: {"n": 0, "actionable": 0})
    types: dict = defaultdict(lambda: {"n": 0, "mix": defaultdict(int)})
    for hb, sev, cat, act, state, source, type_id, name, n in rollup:
        now_k["total"] += n
        severity[sev] += n
        sources[source] += n
        cats[cat]["n"] += n
        t = types[(type_id, name)]
        t["n"] += n
        t["mix"][(sev, cat)] += n
        if hb is not None:
            series[hb + ":00" if hourly else hb[:10]][sev] += n
        if act:
            now_k["actionable"] += n
            cats[cat]["actionable"] += n
            states[state] += n
            now_k["open_alerts"] += n if state != "resolved" else 0
            now_k["p1"] += n if sev == "P1" else 0
            if hb is not None:
                h = int(hb[11:13])
                score[cat][h] += n
                worst[(cat, h)] = min(worst.get((cat, h)) or sev, sev) if sev else worst.get((cat, h))
    volume = [{"t": b, **v} for b, v in sorted(series.items())]
    score_rows = [{"category": c, "hours": [{"h": h, "n": hours.get(h, 0), "worst": worst.get((c, h))} for h in range(24)],
                   "total": sum(hours.values())} for c, hours in score.items()]
    score_rows.sort(key=lambda r: -r["total"])
    categories = sorted(({"category": c, **v} for c, v in cats.items()), key=lambda r: -r["n"])
    top_types = []
    for (type_id, name), t in sorted(types.items(), key=lambda kv: (-kv[1]["n"], str(kv[0])))[:10]:
        sev, cat = max(t["mix"].items(), key=lambda kv: kv[1])[0]
        top_types.append({"type_id": type_id, "name": name, "severity": sev, "category": cat, "n": t["n"]})
    severity, states, sources = dict(severity), dict(states), dict(sources)
    bucket = "%H" if hourly else ""

    dev_tot: dict = defaultdict(lambda: [0, 0])
    site_tot: dict = defaultdict(lambda: {"n": 0, "p1": 0, "devices": set()})
    for device_id, site_code, n, p1 in places:
        if device_id is not None:
            dev_tot[device_id][0] += n
            dev_tot[device_id][1] += p1
        if site_code is not None:
            st = site_tot[site_code]
            st["n"] += n
            st["p1"] += p1
            if device_id is not None:
                st["devices"].add(device_id)
    known = {}
    if dev_tot:  # only devices still in the inventory are ranked (as the inventory join did before)
        ranked = sorted(dev_tot.items(), key=lambda kv: (-kv[1][0], kv[0]))  # ties: lowest id, stable between reloads
        for chunk in range(0, len(ranked), 900):
            ids = [d for d, _ in ranked[chunk:chunk + 900]]
            known.update({r["id"]: r for r in db.rows(conn, f"SELECT id, name, role, ip, site_code FROM devices "
                                                            f"WHERE id IN ({','.join('?' * len(ids))})", ids)})
            if len([d for d, _ in ranked[:chunk + 900] if d in known]) >= 8:
                break
        top_devices = [{**known[d], "n": t[0], "p1": t[1], "flapping": osum["flapping_devices"].get(d, 0)}
                       for d, t in ranked if d in known][:8]
    else:
        top_devices = []
    site_rows = {r["code"]: r for r in db.rows(conn, "SELECT code, label, state FROM sites")}
    top_sites = [{"code": code, "label": (site_rows.get(code) or {}).get("label"), "state": (site_rows.get(code) or {}).get("state"),
                  "n": t["n"], "devices": len(t["devices"]), "p1": t["p1"]}
                 for code, t in sorted(site_tot.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:8]]
    states_map: dict = defaultdict(lambda: {"n": 0, "sites": 0, "p1": 0})
    for code, t in site_tot.items():
        st = (site_rows.get(code) or {}).get("state")
        if st is not None:
            states_map[st]["n"] += t["n"]
            states_map[st]["sites"] += 1
            states_map[st]["p1"] += t["p1"]
    by_state = [{"state": st, **v} for st, v in states_map.items()]
    hot = db.rows(conn, f"""SELECT id, ts, name, severity, category, device_name, site_code, message, state, transition, source
                           FROM events WHERE {where} AND actionable=1 AND state<>'resolved' AND severity IN ('P1','P2')
                           ORDER BY ts DESC, source_id DESC LIMIT 6""", params)

    tickets = db.one(conn, """SELECT COUNT(*) total, SUM(is_open) open,
                                  (SELECT COUNT(DISTINCT ticket_id) FROM ticket_links) linked,
                                  CAST(AVG(resolve_minutes) AS INTEGER) avg_resolve
                              FROM tickets""")
    kinds = db.rows(conn, "SELECT kind, COUNT(*) n, SUM(is_open) open FROM tickets GROUP BY kind ORDER BY n DESC")

    result = {
        "window": w,
        "kpis": {
            "events": now_k["total"], "actionable": now_k["actionable"], "open_alerts": now_k["open_alerts"],
            "p1": now_k["p1"], "devices": now_k["devices"], "sites": now_k["sites"],
            "signal_pct": round(100 * now_k["actionable"] / now_k["total"], 1) if now_k["total"] else 0,
            "mttr_minutes": osum["mttr_minutes"], "p90_minutes": osum["p90_minutes"],
            "outages": osum["closed"], "still_down": osum["open"], "flapping": len(osum["flapping_devices"]),
        },
        "previous": prev_k,
        "volume": volume, "bucket": "hour" if "%H" in bucket else "day",
        "score": score_rows, "severity": severity, "categories": categories, "states": states, "sources": sources,
        "top_devices": top_devices, "top_sites": top_sites, "by_state": by_state, "top_types": top_types, "hot": hot,
        "tickets": {**(tickets or {}), "kinds": kinds},
        "labels": {"severity": dict(cfg.classification.severity_labels.items())},
    }
    return result
