"""Ticket-history ranking and the built-in recommendation engine (no external AI required)."""
from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import timedelta

from .. import db
from ..cache import cache
from ..config import cfg
from . import correlate as K
from . import textmine as T

R = cfg.recommend
_LINK_REASON = {"ci": "lists this device as its configuration item", "device": "names this device",
                "ip": "mentions this device's IP {value}", "site": "mentions site {value}"}


def _words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text or "")}


def _gap(minutes: int | None) -> str:
    if minutes is None:
        return "near"
    m = abs(minutes)
    span = f"{m} min" if m < 120 else f"{m / 60:.1f} h"
    return f"{span} after" if minutes >= 0 else f"{span} before"


def _ticket_range(conn) -> dict:
    return cache.get(conn, "ticket_range", None,
                     lambda: db.one(conn, "SELECT MIN(created_at) first, MAX(created_at) last FROM tickets") or {})


def _time_comparable(conn, ev_ts) -> bool:
    """Ticket timing only means something when the alert falls inside the period the ticket export covers."""
    if not ev_ts:
        return False
    r = _ticket_range(conn)
    lo, hi = K.parse_ts(r.get("first")), K.parse_ts(r.get("last"))
    if not lo or not hi:
        return False
    return lo - timedelta(hours=R.time_after_hours) <= ev_ts <= hi + timedelta(hours=R.time_before_hours)


def time_context(conn, event: dict) -> dict:
    r = _ticket_range(conn)
    return {"compared": _time_comparable(conn, K.parse_ts(event.get("ts"))), "tickets_first": r.get("first"), "tickets_last": r.get("last")}


def related_tickets(conn, event: dict, device: dict | None, limit: int | None = None) -> list[dict]:
    limit = limit or R.max_tickets
    cand: dict[int, dict] = {}

    def slot(tid):
        return cand.setdefault(tid, {"link": 0.0, "text": 0.0, "time": 0.0, "boost": 0.0, "reasons": []})

    device_id = (device or {}).get("id") or 0
    site = event.get("site_code")
    for l in db.rows(conn, """SELECT ticket_id, kind, value, confidence, device_id, evidence, gap_minutes FROM ticket_links
                              WHERE (device_id = ? AND device_id <> 0) OR (site_code = ? AND ? IS NOT NULL)""",
                     (device_id, site, site)):
        c = slot(l["ticket_id"])
        if l["device_id"] and l["device_id"] != device_id:
            conf, why = 0.5, f"concerns another device at site {site}"
        else:
            conf, why = l["confidence"], _LINK_REASON[l["kind"]].format(value=l["value"])
        if conf > c["link"]:
            c["link"] = conf
        if why not in [r["text"] for r in c["reasons"]]:
            c["reasons"].append({"kind": l["kind"] if conf >= 0.6 else "nearby", "text": why})
        if l["evidence"] == "confirmed" and not any(r["kind"] == "confirmed" for r in c["reasons"]):
            c["reasons"].append({"kind": "confirmed", "text": f"opened {_gap(l['gap_minutes'])} an alert on the linked "
                                                              f"{'device' if l['device_id'] else 'site'}"})

    role = (device or {}).get("role") or ""
    terms = T.query_terms(event.get("name", ""), event.get("message", ""), role)
    if terms:
        match = " OR ".join(f'"{t}"' for t in terms)
        try:
            for r in db.rows(conn, "SELECT rowid id FROM tickets_fts WHERE tickets_fts MATCH ? ORDER BY bm25(tickets_fts) LIMIT 40", (match,)):
                slot(r["id"])
        except Exception:
            pass
    if not cand:
        return []

    ids = list(cand)
    tickets = {t["id"]: t for t in db.rows(conn, f"""SELECT id, number, kind, state, is_open, created_at, closed_at, resolve_minutes,
                    assignment_group, assigned_to, short_description, description, work_notes, close_notes, resolution, incident_start
                    FROM tickets WHERE id IN ({','.join('?' * len(ids))})""", ids)}
    helpful = Counter(r["ticket_number"] for r in db.rows(conn, """SELECT f.ticket_number FROM feedback f JOIN events e ON e.id=f.event_id
                    WHERE f.verdict='helpful' AND f.ticket_number IS NOT NULL AND (e.device_id=? OR e.type_id=?)""",
                                                          (device_id, event.get("type_id"))))
    ev_ts = K.parse_ts(event.get("ts"))
    time_known = _time_comparable(conn, ev_ts)
    w_link, w_text, w_time = R.weight_link, R.weight_text, R.weight_time
    if not time_known:  # tickets do not cover this alert's period: timing is unknown, not "far apart"
        w_link, w_text, w_time = R.weight_link / (R.weight_link + R.weight_text), R.weight_text / (R.weight_link + R.weight_text), 0.0
    term_set = set(terms)
    out = []
    for tid, c in cand.items():
        t = tickets.get(tid)
        if not t:
            continue
        shared = term_set & _words(" ".join(filter(None, [t["short_description"], t["description"], t["work_notes"]])))
        c["text"] = min(len(shared) / max(min(len(term_set), 6), 1), 1.0)
        if c["link"] == 0 and len(shared) < R.min_shared_terms:
            continue  # wording alone is too weak unless several specific words line up
        if shared:
            c["reasons"].append({"kind": "text", "text": "shares " + ", ".join(sorted(shared)[:5])})
        created = K.parse_ts(t["created_at"])
        start = K.parse_ts(t["incident_start"])
        if time_known and ev_ts and start and (c["link"] > 0 or c["text"] >= 0.3):
            hours = (start - ev_ts).total_seconds() / 3600  # the ticket states when its incident began
            window = 2 * cfg.linking.start_window_minutes / 60
            if abs(hours) <= window:
                c["time"] = 1 - abs(hours) / window * 0.5
                mins = int(round(hours * 60))
                c["reasons"].append({"kind": "time", "text": f"incident start stated {abs(mins)} min {'after' if mins >= 0 else 'before'} this alert"})
        elif time_known and ev_ts and created and (c["link"] > 0 or c["text"] >= 0.3):
            hours = (created - ev_ts).total_seconds() / 3600
            if -R.time_before_hours <= hours <= R.time_after_hours:
                c["time"] = max(0.0, 1 - abs(hours) / max(R.time_after_hours, 1)) if hours >= 0 else 0.8
                mins = int(round(hours * 60))
                c["reasons"].append({"kind": "time", "text": f"opened {abs(mins)} min {'after' if mins >= 0 else 'before'} this alert"})
        if not t["is_open"] and t["resolution"]:
            c["boost"] += R.resolved_bonus
        if helpful.get(t["number"]):
            c["boost"] += 0.15
            c["reasons"].append({"kind": "feedback", "text": f"marked helpful by analysts {helpful[t['number']]}×"})
        score = w_link * c["link"] + w_text * c["text"] + w_time * c["time"] + c["boost"]
        if score < R.min_score:
            continue
        out.append({
            "id": tid, "number": t["number"], "kind": t["kind"], "state": t["state"], "is_open": t["is_open"],
            "created_at": t["created_at"], "closed_at": t["closed_at"], "resolve_minutes": t["resolve_minutes"],
            "assignment_group": t["assignment_group"], "assigned_to": t["assigned_to"],
            "short_description": t["short_description"], "resolution": t["resolution"],
            "fixes": T.action_sentences(t["close_notes"] or t["work_notes"], 2, 0 if t["is_open"] else 1.5),
            "score": round(min(score, 1.0) * 100), "parts": {k: round(c[k], 2) for k in ("link", "text", "time", "boost")},
            "time_compared": time_known,
            "reasons": c["reasons"][:5],
        })
    out.sort(key=lambda x: x["created_at"] or "", reverse=True)  # newest first among equals
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def _fmt(step: str, ctx: dict) -> str:
    try:
        return step.format(**ctx)
    except (KeyError, IndexError):
        return step


def build(conn, event: dict, device: dict | None, site: dict | None, analysis: dict, history: list[dict], checks: dict | None) -> dict:
    name = (device or {}).get("name") or event.get("device_name") or "the device"
    site_label = (f"site {event['site_code']}" + (f" ({site['label']})" if site and site.get("label") else "")) if event.get("site_code") else "the site"
    iface = analysis.get("interface")
    ctx = {"device": name, "ip": (device or {}).get("ip") or event.get("ip") or "its IP", "site": event.get("site_code") or "—",
           "site_label": site_label, "interface": iface or "", "role": (device or {}).get("role") or "device"}
    signals, steps = [], []
    blast = analysis.get("blast_radius", [])
    flaps = analysis.get("flap_cycles", 0)
    outage = analysis.get("outage")
    recurrence = analysis.get("recurrence", {})
    ping = (checks or {}).get("ping") or {}
    open_tickets = [h for h in history if h["is_open"] and h["kind"] in R.dedupe_kinds
                    and (h["parts"]["link"] >= 0.8 or (h["parts"]["link"] >= 0.6 and h["parts"]["time"] > 0))]
    best = history[0] if history else None

    if blast:
        n = len({b["device_id"] for b in blast})
        signals.append({"tone": "critical", "weight": 3, "text": f"{n} other device{'s' if n > 1 else ''} at {site_label} went down within ±{cfg.correlation.blast_radius_minutes} min"})
    if flaps >= cfg.correlation.flap_threshold:
        signals.append({"tone": "warning", "weight": 2, "text": f"Flapping: {flaps} short down/up cycles in the last {cfg.correlation.health_window_days} days"})
    if outage and outage.get("minutes") is not None:
        signals.append({"tone": "good", "weight": 1, "text": f"Recovered after {outage['minutes']:g} min ({outage['up_ts'][11:19]})"})
    elif outage:
        signals.append({"tone": "critical", "weight": 2, "text": "No matching recovery event yet — still down in the data"})
    if ping:
        if ping.get("reachable") is False:
            signals.append({"tone": "critical", "weight": 2, "text": f"No reply to ping right now ({ping.get('loss_pct', 100):g}% loss)"})
        elif ping.get("reachable"):
            signals.append({"tone": "good", "weight": 1, "text": f"Answers ping now (avg {ping.get('avg_ms')} ms)"})
    if recurrence.get("same_type_device", 0) > 1:
        signals.append({"tone": "warning", "weight": 1, "text": f"Seen {recurrence['same_type_device']} times on this device in {cfg.correlation.health_window_days} days"})
    if best and best["score"] >= 55:
        signals.append({"tone": "info", "weight": 2, "text": f"Closely matches {best['number']} ({best['score']}% match)"})
    if open_tickets:
        signals.append({"tone": "info", "weight": 2, "text": f"Open ticket already covers this: {open_tickets[0]['number']}"})

    cat = event.get("category") or "other"
    transition = event.get("transition")
    if blast:
        hypothesis = (f"Site-level disruption at {site_label}: {len(blast) + 1} devices dropped together. "
                      f"An upstream cause — site power, the WAN circuit or a core/distribution switch — is more likely than a fault on {name} itself.")
    elif flaps >= cfg.correlation.flap_threshold:
        hypothesis = (f"{name} is flapping. Repeated short outages point to physical-layer instability: "
                      "cabling or optics, PoE budget, or unstable power at the device.")
    elif transition == "down" and ping.get("reachable") is False:
        hypothesis = f"{name} is hard down and still unreachable. Likely causes: loss of power, a failed uplink or a hung device."
    elif transition == "down" and outage and outage.get("minutes") is not None and outage["minutes"] <= 15:
        hypothesis = (f"{name} dropped and recovered within {outage['minutes']:g} min — a transient. "
                      "Check for a reboot, power blip or upstream link flap before closing.")
    elif transition == "up":
        hypothesis = f"Recovery notice for {name}. Confirm the matching outage is closed and capture the cause in the ticket."
    else:
        hypothesis = {
            "interface": f"Link-level fault on {name}{' ' + iface if iface else ''}: cable, optic, far-end device or a configuration change.",
            "power": f"Power-protection event on {name}: utility power, UPS battery health or UPS load.",
            "wireless": f"Wireless fault on {name}: AP join/CAPWAP state, PoE supply or controller capacity.",
            "routing": f"WAN/routing fault at {site_label}: carrier circuit, BGP neighbour or SD-WAN path.",
            "hardware": f"Hardware health degradation on {name}: fan, PSU, temperature or stack member.",
            "performance": f"Resource pressure on {name}: CPU, memory or link utilisation above normal.",
            "connectivity": f"Reachability loss for {name}: power, uplink or the device itself.",
        }.get(cat, f"{event.get('name')} on {name}. Review the message and timeline for the trigger.")
    if best and best.get("resolution") and best["score"] >= 45:
        hypothesis += f" Last time ({best['number']}): {best['resolution'][:220]}"

    if open_tickets:
        steps.append({"text": f"Update the open ticket {open_tickets[0]['number']} instead of raising a duplicate.", "source": "dedupe"})
    if blast:
        steps.append({"text": f"Treat as one site incident for {site_label}: link the {len(blast) + 1} device alerts to a single parent ticket.", "source": "correlation"})
        steps.append({"text": f"Check the WAN circuit, core switch and power for {site_label} first.", "source": "correlation"})
    if flaps >= cfg.correlation.flap_threshold:
        steps.append({"text": "Pull interface/PoE error counters and the device log for the flap times; reseat or replace the suspect cable or optic.", "source": "correlation"})
    playbook = cfg.playbooks.get(cat) or cfg.playbooks.get("other")
    for step in playbook:
        steps.append({"text": _fmt(step, ctx), "source": "playbook"})
    proven = []
    for h in [h for h in history if h["score"] >= R.min_fix_score][:3]:
        for fix in h["fixes"][:1]:
            proven.append({"text": fix, "source": h["number"]})
    steps.extend(proven)

    weight = sum(s["weight"] for s in signals)
    confidence = min(95, 30 + weight * 7 + (best["score"] // 4 if best else 0))
    label = "High" if confidence >= 75 else "Medium" if confidence >= 50 else "Low"
    strong = [h for h in history if h["score"] >= R.min_fix_score]
    closed = [h["resolve_minutes"] for h in strong if h["resolve_minutes"] and not h["is_open"]]
    groups = Counter(h["assignment_group"] for h in (strong or history) if h["assignment_group"])
    return {
        "provider": "NOCTURNE engine",
        "hypothesis": hypothesis,
        "confidence": confidence, "confidence_label": label,
        "signals": signals,
        "steps": steps,
        "assignment_group": groups.most_common(1)[0][0] if groups else None,
        "expected_minutes": round(statistics.median(closed)) if closed else None,
        "based_on": [h["number"] for h in strong[:3]],
        "work_note": _work_note(event, name, site_label, hypothesis, signals, steps, checks),
    }


def _work_note(event, name, site_label, hypothesis, signals, steps, checks) -> str:
    lines = [f"[NOCTURNE triage] {event.get('severity')} {event.get('name')} on {name} ({site_label}) at {event.get('ts') or '—'}",
             f"Hypothesis: {hypothesis}"]
    if signals:
        lines.append("Evidence: " + "; ".join(s["text"] for s in signals))
    if checks:
        p = checks.get("ping") or {}
        lines.append(f"Checks ({checks.get('mode')}): ping {'OK' if p.get('reachable') else 'FAILED'}, "
                     f"traceroute {'complete' if (checks.get('traceroute') or {}).get('completed') else 'incomplete'}")
    lines.append("Next steps:")
    lines += [f"  {i}. {s['text']}" for i, s in enumerate(steps[:6], start=1)]
    return "\n".join(lines)


def analysis(conn, event: dict, device: dict | None) -> dict:
    """Stages 1–2: context, timeline, outage pairing, blast radius, recurrence."""
    out = {"interface": None, "timeline": [], "outage": None, "blast_radius": [], "flap_cycles": 0, "recurrence": {}}
    from .classify import interface_of
    out["interface"] = interface_of(event.get("message") or "")
    if device:
        out["timeline"] = K.timeline(conn, device["id"], event.get("ts"))
        window_start = K.shift(event["ts"], days=-cfg.correlation.health_window_days) if event.get("ts") else None
        outs = K.outages(conn, window_start, K.shift(event["ts"], days=2) if event.get("ts") else None, device["id"])
        summary = K.outage_summary(outs)
        out["flap_cycles"] = sum(1 for o in outs if o["minutes"] is not None and o["minutes"] <= cfg.correlation.flap_window_minutes)
        out["outage"] = next((o for o in outs if o["down_id"] == event["id"]), None)
        if not out["outage"] and event.get("transition") == "up":
            out["outage"] = next((o for o in outs if o["up_id"] == event["id"]), None)
        out["outages_recent"] = sorted([o for o in outs if o["minutes"] is not None], key=lambda o: o["down_ts"])[-12:]
        out["mttr_device"] = summary["mttr_minutes"]
        if event.get("ts"):
            start = K.shift(event["ts"], days=-cfg.correlation.health_window_days)
            out["recurrence"] = {
                "same_type_device": db.scalar(conn, "SELECT COUNT(*) FROM events WHERE device_id=? AND type_id IS ? AND ts BETWEEN ? AND ?",
                                              (device["id"], event.get("type_id"), start, event["ts"]), 0),
                "same_type_site": db.scalar(conn, "SELECT COUNT(*) FROM events WHERE site_code=? AND type_id IS ? AND ts BETWEEN ? AND ?",
                                            (event.get("site_code"), event.get("type_id"), start, event["ts"]), 0) if event.get("site_code") else 0,
                "by_hour": [r["n"] for r in db.rows(conn, """WITH RECURSIVE h(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM h WHERE x<23)
                            SELECT COALESCE(c.n,0) n FROM h LEFT JOIN (SELECT CAST(strftime('%H', ts) AS INTEGER) hr, COUNT(*) n FROM events
                            WHERE device_id=? GROUP BY hr) c ON c.hr = h.x ORDER BY h.x""", (device["id"],))],
            }
    out["blast_radius"] = K.blast_radius(conn, event)
    return out
