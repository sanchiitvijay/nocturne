"""Ties tickets to the inventory: configuration item, device names, IPs and site codes in the text."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from ... import db
from ...config import cfg
from .. import textmine as T

W = cfg.linking


def relink(conn, report=None) -> dict:
    devices = db.rows(conn, "SELECT id, name_key, ip, site_code FROM devices")
    by_name = {d["name_key"]: d["id"] for d in devices}
    by_ip: dict[str, list[int]] = defaultdict(list)
    for d in devices:
        if d["ip"]:
            by_ip[d["ip"]].append(d["id"])
    known_sites = {r["code"] for r in db.rows(conn, "SELECT code FROM sites")}

    tickets = db.rows(conn, "SELECT id, short_description, description, work_notes, close_notes, cmdb_ci FROM tickets")
    links, kinds = [], Counter()
    linked_tickets, linked_devices = set(), set()
    for i, t in enumerate(tickets):
        blob = "\n".join(x for x in (t["short_description"], t["description"], t["work_notes"], t["close_notes"]) if x)
        found: dict[tuple, tuple] = {}
        ci = (t["cmdb_ci"] or "").strip().lower()
        if ci and ci in by_name:
            found[("ci", ci, by_name[ci])] = (W.ci, None)
        for name_key, dev_id in T.devices_in_text(blob, by_name).items():
            found.setdefault(("device", name_key, dev_id), (W.device_name, None))
        for ip in T.ips_in_text(blob):
            for dev_id in by_ip.get(ip, []):
                found.setdefault(("ip", ip, dev_id), (W.ip_address, None))
        for site in T.sites_in_text(blob):
            if site in known_sites:
                found[("site", site, 0)] = (W.site_code, site)
        for (kind, value, dev_id), (conf, site) in found.items():
            links.append((t["id"], kind, value, dev_id, site, conf))
            kinds[kind] += 1
            linked_tickets.add(t["id"])
            if dev_id:
                linked_devices.add(dev_id)
        if report and i % 200 == 0:
            report(i / max(len(tickets), 1))
    conn.execute("DELETE FROM ticket_links")
    conn.executemany("INSERT OR IGNORE INTO ticket_links(ticket_id, kind, value, device_id, site_code, confidence) "
                     "VALUES (?,?,?,?,?,?)", links)
    # Device-level links also imply the device's site.
    conn.execute("""UPDATE ticket_links SET site_code = (SELECT site_code FROM devices WHERE devices.id = ticket_links.device_id)
                    WHERE device_id <> 0 AND site_code IS NULL""")
    evidence = _time_evidence(conn)
    return {
        "links": len(links), "by_kind": dict(kinds), "tickets_linked": len(linked_tickets),
        "tickets_total": len(tickets), "devices_linked_directly": len(linked_devices),
        "ticket_coverage_pct": round(100 * len(linked_tickets) / len(tickets), 1) if tickets else 0,
        "time_evidence": evidence,
    }


def _time_evidence(conn) -> dict:
    """Corroborate links with alert timing, but only where imported events actually cover the ticket's opening.

    Days without imported events say nothing about whether the device was alerting, so those links keep their
    text-based confidence (evidence NULL) instead of being treated as contradicted.
    """
    covered = {r["d"] for r in db.rows(conn, "SELECT DISTINCT substr(ts, 1, 10) d FROM events WHERE source='import' AND ts IS NOT NULL")}
    before, after = timedelta(hours=W.confirm_hours_before), timedelta(hours=W.confirm_hours_after)
    out = Counter()
    updates = []
    around = timedelta(minutes=W.start_window_minutes)
    for l in db.rows(conn, """SELECT l.id, l.kind, l.device_id, l.site_code, l.confidence, t.created_at, t.incident_start
                              FROM ticket_links l JOIN tickets t ON t.id = l.ticket_id"""):
        start = _parse(l["incident_start"])
        opened = start or _parse(l["created_at"])  # a validated stated start pins the incident tighter than the opening
        if not opened:
            out["ticket_without_date"] += 1
            continue
        lo, hi = (opened - around, opened + around) if start else (opened - before, opened + after)
        days = {(lo + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((hi.date() - lo.date()).days + 1)}
        if not days & covered:
            out["outside_event_data"] += 1
            continue
        column, value = ("device_id", l["device_id"]) if l["device_id"] else ("site_code", l["site_code"])
        hit = db.one(conn, f"""SELECT id, ts FROM events WHERE {column} = ? AND source='import' AND actionable = 1
                               AND ts BETWEEN ? AND ? ORDER BY severity, transition = 'down' DESC,
                               ABS(julianday(?) - julianday(ts)) LIMIT 1""",
                     (value, lo.strftime("%Y-%m-%d %H:%M:%S"), hi.strftime("%Y-%m-%d %H:%M:%S.999"), opened.strftime("%Y-%m-%d %H:%M:%S")))
        if hit:
            gap = int((opened - _parse(hit["ts"])).total_seconds() // 60)
            updates.append((min(0.99, l["confidence"] + W.confirmed_bonus), "confirmed", gap, hit["id"], l["id"]))
            out["confirmed"] += 1
        elif days <= covered:  # the whole window is covered, so the silence is real
            conf = W.site_without_alerts if l["kind"] == "site" else l["confidence"]
            updates.append((conf, "no_alerts", None, None, l["id"]))
            out["no_alerts"] += 1
        else:
            out["partly_covered"] += 1
    conn.executemany("UPDATE ticket_links SET confidence=?, evidence=?, gap_minutes=?, event_id=? WHERE id=?", updates)
    return dict(out)


def _parse(ts: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(ts[:19]) if ts else None
    except ValueError:
        return None
