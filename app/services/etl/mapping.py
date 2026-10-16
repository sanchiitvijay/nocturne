"""Dataset detection and column mapping: header aliases first, then content sniffing.

A mapping is {canonical_field: column_index}. Unmapped columns are preserved per row in "extra".
"""
from __future__ import annotations

import re
import statistics

from ...config import cfg
from . import timeparse as TP

TIME_RX = re.compile(r"\d{1,2}:\d{2}(:\d{2})?")
SITE_RX = re.compile(r"^\d{3,5}$")
IP_RX = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# Fields that identify a dataset and the ones an import cannot run without.
SIGNATURE = {
    "events": {"source_id": 2, "time": 3, "type_id": 2, "type_name": 1, "device_name": 2, "ip": 1, "status_code": 1, "node_id": 1},
    "tickets": {"number": 3, "short_description": 3, "state": 1, "created_at": 2, "work_notes": 2, "assignment_group": 1},
}
REQUIRED = {"events": [["time"], ["message", "type_name", "type_id"]], "tickets": [["number"], ["short_description", "description"]]}

FIELD_HELP = {
    "events": {
        "source_id": "Event ID from the monitoring tool (makes re-imports update instead of duplicate)",
        "time": "Event timestamp — date and time, e.g. 19-05-2026 20:00 (required)",
        "date": "Separate date column, only when the export splits date and time",
        "type_id": "Numeric event type",
        "type_name": "Event type name (e.g. Node Down)",
        "message": "Full event message / detail text",
        "node_id": "Monitoring node ID",
        "device_name": "Device / node name",
        "ip": "Device IP address",
        "machine_type": "Device model",
        "vendor": "Device vendor",
        "status_code": "Current status code of the node",
        "location": "Site address / location text",
        "site_hint": "Site or branch code column",
        "severity": "Severity from the source (optional; rules decide otherwise)",
    },
    "tickets": {
        "number": "Ticket number (INC/RITM/TASK/CHG…)",
        "state": "Ticket state",
        "priority": "Priority",
        "opened_by": "Opened by / caller",
        "created_at": "Created on",
        "updated_at": "Updated on",
        "closed_at": "Closed / resolved at",
        "assignment_group": "Assignment group",
        "assigned_to": "Assigned to",
        "short_description": "Short description / title",
        "description": "Description",
        "work_notes": "Work notes journal",
        "work_notes_list": "Work notes list / watch list",
        "close_notes": "Close / resolution notes",
        "category": "Category",
        "cmdb_ci": "Configuration item (device)",
    },
}


def norm(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (header or "").lower())


def aliases(dataset: str) -> dict[str, list[str]]:
    section = cfg.etl.events.aliases if dataset == "events" else cfg.etl.tickets.aliases
    return {k: [norm(a) for a in v] for k, v in section.items()}


def _alias_mapping(headers: list[str], dataset: str) -> dict[str, dict]:
    normed = [norm(h) for h in headers]
    taken, mapping = set(), {}
    # Resolve fields in alias-priority order: exact first alias wins, then later aliases.
    table = aliases(dataset)
    for depth in range(max(len(v) for v in table.values())):
        for field, names in table.items():
            if field in mapping or depth >= len(names):
                continue
            for idx, h in enumerate(normed):
                if idx not in taken and h == names[depth]:
                    mapping[field] = {"col": idx, "method": "header", "confidence": round(1 - depth * 0.05, 2)}
                    taken.add(idx)
                    break
    return mapping


def detect(headers: list[str]) -> tuple[str, float, dict[str, dict]]:
    best = ("unknown", 0.0, {})
    for dataset, weights in SIGNATURE.items():
        mapping = _alias_mapping(headers, dataset)
        score = sum(w for f, w in weights.items() if f in mapping) / sum(weights.values())
        if score > best[1]:
            best = (dataset, round(score, 2), mapping)
    if best[1] < 0.3:
        return "unknown", best[1], best[2]
    return best


def _has_date(value: str) -> bool:
    return any(TP.parse_moment(value, df)[0] is not None for df in (False, True))


def _profile(rows: list[list[str]], idx: int) -> dict:
    values = [r[idx].strip() for r in rows if idx < len(r)]
    filled = [v for v in values if v and v.upper() != "NULL"]
    if not filled:
        return {"fill": 0.0, "distinct": 0.0, "avg_len": 0, "site": 0, "time": 0, "stamp": 0, "date": 0, "time_only": 0, "ip": 0}
    n = len(filled)
    return {
        "fill": n / max(len(values), 1),
        "distinct": len(set(filled)) / n,
        "avg_len": statistics.mean(len(v) for v in filled),
        "site": sum(bool(SITE_RX.match(v)) for v in filled) / n,
        "time": sum(bool(TIME_RX.search(v)) for v in filled) / n,
        "stamp": sum(_has_date(v) and bool(TIME_RX.search(v)) for v in filled) / n,
        "date": sum(_has_date(v) for v in filled) / n,
        "time_only": sum(TP.time_only(v) for v in filled) / n,
        "ip": sum(bool(IP_RX.match(v)) for v in filled) / n,
    }


def propose(headers: list[str], rows: list[list[str]], dataset: str | None = None) -> dict:
    """Detect the dataset and propose a mapping with reasons the admin can review."""
    detected, score, mapping = detect(headers)
    if dataset and dataset != detected:
        mapping = _alias_mapping(headers, dataset)
        detected = dataset
    notes = []
    if detected == "events":
        mapping, notes = _sniff_events(headers, rows, mapping)
    mapped_cols = {m["col"] for m in mapping.values()}
    unmapped = [{"col": i, "header": h} for i, h in enumerate(headers)
                if i not in mapped_cols and _profile(rows, i)["fill"] > 0]
    for field, m in mapping.items():
        m["header"] = headers[m["col"]]
    return {
        "dataset": detected,
        "confidence": score,
        "mapping": mapping,
        "unmapped": unmapped,
        "notes": notes,
        "missing_required": missing_required(detected, {f: m["col"] for f, m in mapping.items()}),
        "fields": FIELD_HELP.get(detected, {}),
    }


def _sniff_events(headers, rows, mapping):
    notes = []
    taken = {m["col"] for m in mapping.values()}
    free = [i for i in range(len(headers)) if i not in taken]
    profiles = {i: _profile(rows, i) for i in range(len(headers))}

    # SolarWinds-style exports put the event-type name under "Message" and the real text in an unnamed column.
    if "message" in mapping:
        mcol = mapping["message"]["col"]
        mp = profiles[mcol]
        long_cols = [i for i in free if profiles[i]["fill"] > 0.6 and profiles[i]["avg_len"] > max(30, mp["avg_len"] * 1.5)]
        if long_cols and mp["avg_len"] < 40 and mp["distinct"] < 0.5 and "type_name" not in mapping:
            target = max(long_cols, key=lambda i: profiles[i]["avg_len"])
            mapping["type_name"] = {"col": mcol, "method": "content", "confidence": 0.85}
            mapping["message"] = {"col": target, "method": "content", "confidence": 0.85}
            free.remove(target)
            notes.append(f"“{headers[mcol]}” holds short event-type names, so the long free-text column "
                         f"“{headers[target]}” was mapped as the message.")
    elif free:
        long_cols = [i for i in free if profiles[i]["fill"] > 0.6 and profiles[i]["avg_len"] > 30]
        if long_cols:
            target = max(long_cols, key=lambda i: profiles[i]["avg_len"])
            mapping["message"] = {"col": target, "method": "content", "confidence": 0.7}
            free.remove(target)
            notes.append(f"No message header found; “{headers[target]}” looks like free text and was mapped as the message.")

    if "site_hint" not in mapping:
        for i in free:
            if profiles[i]["fill"] > 0.3 and profiles[i]["site"] > 0.8:
                mapping["site_hint"] = {"col": i, "method": "content", "confidence": 0.6}
                free.remove(i)
                notes.append(f"“{headers[i]}” contains 3–5 digit codes and was mapped as a site hint. "
                             "Site codes are taken from device names first; this column is only a fallback.")
                break

    if "time" not in mapping:
        stamps = [i for i in free if profiles[i]["stamp"] > 0.8]
        if stamps:
            i = max(stamps, key=lambda c: profiles[c]["stamp"])
            mapping["time"] = {"col": i, "method": "content", "confidence": 0.75}
            free.remove(i)
            notes.append(f"“{headers[i]}” holds dates with times and was mapped as the event timestamp.")
    if "time" in mapping and "date" not in mapping and profiles[mapping["time"]["col"]]["time_only"] > 0.5:
        dates = [i for i in free if profiles[i]["date"] > 0.8 and profiles[i]["time"] < 0.2]
        if dates:
            mapping["date"] = {"col": dates[0], "method": "content", "confidence": 0.7}
            free.remove(dates[0])
            notes.append(f"“{headers[mapping['time']['col']]}” holds times only, so the date column “{headers[dates[0]]}” was added.")
        else:
            notes.append(f"Warning: “{headers[mapping['time']['col']]}” holds times without dates. Every event needs a full date and "
                         "time; rows without one are rejected.")
    if "time" in mapping:
        tcol, dcol = mapping["time"]["col"], mapping.get("date", {}).get("col")
        values = [" ".join(x for x in ((r[dcol] if dcol is not None and dcol < len(r) else ""), (r[tcol] if tcol < len(r) else "")) if x)
                  for r in rows]
        order = TP.detect_order(values)
        notes.append(f"Event timestamps read as {order['order']}: {order['evidence']}.")
    if "ip" not in mapping:
        for i in free:
            if profiles[i]["ip"] > 0.8:
                mapping["ip"] = {"col": i, "method": "content", "confidence": 0.7}
                break
    return mapping, notes


def missing_required(dataset: str, mapping: dict[str, int]) -> list[str]:
    missing = []
    for group in REQUIRED.get(dataset, []):
        if not any(f in mapping and mapping[f] is not None for f in group):
            missing.append(" or ".join(group))
    return missing
