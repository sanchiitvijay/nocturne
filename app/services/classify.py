"""Rule-driven classification. Every rule comes from nocturne.toml; nothing is hard-coded here."""
from __future__ import annotations

import re
from functools import lru_cache

from ..config import cfg

_C = cfg.classification
_SEVERITY_RULES = [(r.level, re.compile(r.pattern, re.I)) for r in _C.severity]
_CATEGORY_RULES = [(r.name, re.compile(r.pattern, re.I)) for r in _C.category]
_ROLE_RULES = [(r.name, re.compile(r.pattern, re.I)) for r in _C.device_role]
_DOWN = re.compile(_C.down_pattern, re.I)
_UP = re.compile(_C.up_pattern, re.I)
_INTERFACE = re.compile(cfg.etl.extract.interface, re.I)
_PLACEHOLDER_TYPE = re.compile(r"^EventType-?\d+$", re.I)
_NULLS = {t.lower() for t in cfg.etl.null_tokens}

SEVERITIES = ["P1", "P2", "P3", "P4"]
CATEGORIES = [r.name for r in _C.category] + ["other"]


def is_null(value) -> bool:
    return value is None or str(value).strip().lower() in _NULLS


def clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _NULLS else text


def catalog_name(type_id: int | None) -> str | None:
    if type_id is None:
        return None
    return cfg.event_types.get(str(type_id))


def is_placeholder_name(name: str | None) -> bool:
    return not name or bool(_PLACEHOLDER_TYPE.match(name.strip()))


def event_name(type_id: int | None, source_name: str | None, overrides: dict | None = None) -> str:
    """Admin override → explicit name in the export → configured catalogue → EventType-N."""
    if overrides and type_id in overrides and overrides[type_id].get("name"):
        if is_placeholder_name(source_name):
            return overrides[type_id]["name"]
    if source_name and not is_placeholder_name(source_name):
        return source_name.strip()
    return catalog_name(type_id) or (f"EventType-{type_id}" if type_id is not None else "Event")


@lru_cache(maxsize=20000)
def severity_of(text: str) -> str:
    for level, rx in _SEVERITY_RULES:
        if rx.search(text):
            return level
    return _C.default_severity


@lru_cache(maxsize=20000)
def _category_in(text: str) -> str | None:
    for name, rx in _CATEGORY_RULES:
        if rx.search(text):
            return name
    return None


def category_of(name: str, message: str) -> str:
    return _category_in(name or "") or _category_in(message or "") or "other"


def transition_of(name: str, message: str) -> str | None:
    """'down' / 'up' / None — the last state word wins ("…Down. Secondary up" → up)."""
    for text in (name or "", message or ""):
        last, kind = -1, None
        for m in _DOWN.finditer(text):
            if m.start() > last:
                last, kind = m.start(), "down"
        for m in _UP.finditer(text):
            if m.start() > last:
                last, kind = m.start(), "up"
        if kind:
            return kind
    return None


def interface_of(message: str) -> str | None:
    m = _INTERFACE.search(message or "")
    return re.sub(r"\s+", "", m.group(1)) if m else None


def pair_key(device_key: str | None, name: str, message: str) -> str | None:
    """Identity shared by a 'down' and the 'up' that clears it: device + interface, or device + node."""
    if not device_key:
        return None
    iface = interface_of(message)
    if iface:
        return f"{device_key}|if:{iface.lower()}"
    text = f"{name} {message}".lower()
    if "node" in text or "responding" in text or "heartbeat" in text:
        return f"{device_key}|node"
    core = _DOWN.sub("", _UP.sub("", (message or name).lower()))
    core = re.sub(r"[^a-z]+", " ", core).strip()[:60]
    return f"{device_key}|{core}" if core else f"{device_key}|node"


@lru_cache(maxsize=20000)
def device_role(text: str) -> str:
    for name, rx in _ROLE_RULES:
        if rx.search(text):
            return name
    return "device"


def classify(type_id, name: str, message: str, overrides: dict | None = None) -> dict:
    """Severity, category, transition and actionability for one event."""
    text = f"{name} :: {message or ''}"[:600]
    override = (overrides or {}).get(type_id) or {}
    severity = override.get("severity") or severity_of(text)
    category = override.get("category") or category_of(name, message)
    actionable = int(severity in _C.actionable_severities and category not in _C.noise_categories)
    return {"severity": severity, "category": category, "actionable": actionable,
            "transition": transition_of(name, message)}


def status_label(code) -> str | None:
    if code is None:
        return None
    return cfg.status_codes.get(str(code), f"Status {code}")


def severity_label(level: str) -> str:
    return _C.severity_labels.get(level, level)
