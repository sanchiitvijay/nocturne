"""Fact extraction from free text: sites, IPs, device names, work-note entries and resolutions."""
from __future__ import annotations

import html
import re
from datetime import datetime

from ..config import cfg

_X = cfg.etl.extract
_SITE_FROM_DEVICE = [re.compile(p) for p in _X.site_from_device]
_SITE_FROM_TEXT = [re.compile(p) for p in _X.site_from_text]
_SITE_LABEL = re.compile(_X.site_label)
_LOCATION_LABEL = re.compile(_X.location_label)
_IPV4 = re.compile(r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?!\.?\d)")
_TAGS = re.compile(r"<[^>]+>")
_TOKEN_SPLIT = re.compile(r"[\s,;:()\[\]{}<>\"'|=]+")
_NOTE_HEAD = re.compile(r"(?m)^(\d{1,2}[-/]\d{1,2}[-/]\d{4} \d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?:\(([^)]*)\))?")
_EMAIL_NOISE = re.compile(r"(?im)^(from|sent|to|cc|subject|caution|importance)\s*:.*$|^caution:.*$")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_STATED_START = re.compile(r"\b(?:start(?:ed)?\s*(?:time|at|date)?|down\s*since|outage\s*start(?:ed)?|issue\s*start(?:ed)?)\s*[:\-]?\s*"
                           r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)", re.I)
_RESOLUTION = re.compile(r"\b(" + "|".join(re.escape(k) for k in cfg.recommend.resolution_keywords) + r")\b", re.I)
_STOP = set("""a an the and or of to in on for at by with from is are was were be been it this that as not no
into via per vs any all its our we you they he she them his her their there here then than so if but up down
please team hi hello thanks thank regards ticket inc ritm task chg noc work notes note
lost primary secondary status changed state event alert device network issue site node down level unit slot
gigabit warning critical severity request timed out has have again response time milliseconds responding stopped
level port""".split())


def site_code(raw) -> str | None:
    """Canonical site code: digits only, zero-padded ("412" and "0412" are the same site)."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if not digits or len(digits) > 6 or int(digits) == 0:
        return None
    return str(int(digits)).zfill(_X.site_width)


def site_from_device(name: str | None) -> str | None:
    if not name:
        return None
    for rx in _SITE_FROM_DEVICE:
        m = rx.search(name)
        if m:
            return site_code(m.group(1))
    return None


def sites_in_text(text: str) -> list[str]:
    found = []
    for rx in _SITE_FROM_TEXT:
        found += [site_code(m) for m in rx.findall(text or "")]
    return sorted({s for s in found if s})


def site_label_from_device(name: str | None) -> tuple[str, str] | None:
    m = _SITE_LABEL.search(name or "")
    if not m:
        return None
    city = re.sub(r"[-_]+", " ", m.group(1)).strip()
    city = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", city)  # SanJuanCapistrano → San Juan Capistrano
    return city.title() if city.islower() else city, m.group(2)


def site_label_from_location(location: str | None) -> tuple[str, str] | None:
    m = _LOCATION_LABEL.search((location or "").replace("_", " "))
    if not m:
        return None
    city = m.group(1).strip().split(",")[-1].strip()
    return (city, m.group(2)) if city and not city[0].isdigit() else None


def clean_location(location: str | None) -> str | None:
    if not location:
        return None
    text = location.split("\n")[0].replace("_", " ")
    text = re.sub(r"\[[A-Z_]+\],?\s*", "", text)
    text = re.sub(r"\s*,\s*", ", ", text).strip(" ,")
    return text if re.search(r"[A-Za-z]{3,}", text or "") else None  # drop anonymised or numeric-only values


def ips_in_text(text: str) -> list[str]:
    return sorted({ip for ip in _IPV4.findall(text or "") if not ip.startswith(("0.", "255.", "127."))})


def valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    m = _IPV4.fullmatch(value.strip())
    return m.group(1) if m else None


def strip_markup(text: str | None) -> str | None:
    if not text:
        return text
    return html.unescape(_TAGS.sub("", text)).strip()


def tokens(text: str) -> set[str]:
    out = set()
    for tok in _TOKEN_SPLIT.split(text or ""):
        tok = tok.strip(".-_/").lower()
        if len(tok) >= _X.min_device_token:
            out.add(tok)
    return out


def devices_in_text(text: str, known: dict[str, int]) -> dict[str, int]:
    """Exact device-name tokens present in the text → {name_key: device_id}."""
    found = {}
    for tok in tokens(text):
        if tok in known:
            found[tok] = known[tok]
        elif "." in tok:  # FQDN mentioned as short name or vice versa
            short = tok.split(".")[0]
            if short in known and len(short) >= _X.min_device_token:
                found[short] = known[short]
    return found


# ── work notes ───────────────────────────────────────────────────────────────

def parse_work_notes(text: str | None) -> list[dict]:
    """Split a ServiceNow journal into timestamped entries (newest first, as exported)."""
    if not text:
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    heads = list(_NOTE_HEAD.finditer(text))
    if not heads:
        body = _tidy(text)
        return [{"at": None, "kind": None, "text": body}] if body else []
    entries = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = _tidy(text[m.end():end])
        if body:
            entries.append({"at": parse_note_time(m.group(1)), "kind": (m.group(2) or "").strip() or None, "text": body})
    return entries


def parse_note_time(raw: str) -> str | None:
    for fmt in ("%m-%d-%Y %H:%M:%S", "%m-%d-%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _tidy(text: str) -> str:
    text = _EMAIL_NOISE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" \n-")


def action_sentences(text: str | None, limit: int = 3, latest_bonus: float = 0.0) -> list[str]:
    """Sentences that describe what was done, ranked by fix-words (and recency when asked)."""
    if not text:
        return []
    entries = parse_work_notes(text) or [{"text": text}]
    scored = []
    for rank, entry in enumerate(entries):
        for sentence in _SENTENCE.split(entry["text"]):
            s = sentence.strip(" -•*\t")
            if not (12 <= len(s) <= 260):
                continue
            hits = len({m.lower() for m in _RESOLUTION.findall(s)})
            if hits:
                bonus = latest_bonus if rank == 0 else 0.0
                scored.append((hits + bonus - rank * 0.05, -len(s), s))
    scored.sort(reverse=True)
    seen, out = set(), []
    for _, _, s in scored:
        key = s.lower()[:60]
        if key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= limit:
            break
    return out


def resolution_summary(close_notes: str | None, work_notes: str | None, is_open: bool) -> str | None:
    if close_notes and close_notes.strip():
        return _tidy(close_notes)[:600]
    entries = parse_work_notes(work_notes)
    actions = action_sentences(work_notes, 2, latest_bonus=0.0 if is_open else 1.5)
    if actions:
        return " · ".join(actions)[:600]
    if entries and not is_open:
        return entries[0]["text"][:400]
    return None


def query_terms(*texts: str, limit: int = 14) -> list[str]:
    """Meaningful words for a full-text similarity query."""
    seen, out = set(), []
    for text in texts:
        for word in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text or ""):
            w = word.lower()
            if w in _STOP or w in seen or w.startswith("eventtype"):
                continue
            seen.add(w)
            out.append(w)
            if len(out) >= limit:
                return out
    return out


def stated_start(text: str | None) -> str | None:
    """The incident start an engineer wrote into the ticket ("Start time: 07/08/26 1:19 AM"), as raw text."""
    m = _STATED_START.search(text or "")
    return m.group(1).strip() if m else None
