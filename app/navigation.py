"""Navigation and UI lookups served to the browser, so the frontend holds no copy of them."""
from __future__ import annotations

from . import security
from .config import cfg
from .services import analytics, classify

# (section, [(page id, label, path, icon, capability)])
NAV = [
    ("Monitor", [
        ("dashboard", "Overview", "/", "pulse", "view_dashboard"),
        ("alerts", "Alerts", "/alerts", "bell", "view_alerts"),
    ]),
    ("Inventory", [
        ("devices", "Devices", "/devices", "chip", "view_inventory"),
        ("sites", "Sites", "/sites", "pin", "view_inventory"),
        ("tickets", "Tickets", "/tickets", "ticket", "view_tickets"),
    ]),
    ("Operations", [
        ("simulator", "Simulator", "/simulator", "bolt", "simulate"),
        ("data", "Data Studio", "/data", "database", "ingest_data"),
        ("admin", "Admin", "/admin", "shield", "manage_users"),
    ]),
]

WINDOW_LABELS = {"24h": "24 hours", "7d": "7 days", "30d": "30 days", "all": "All"}
STATE_LABELS = {"new": "New", "acknowledged": "Acknowledged", "resolved": "Resolved"}
SOURCE_LABELS = {"import": "Imported", "simulation": "Simulated", "custom": "Custom"}


def nav_for(user: dict) -> list[dict]:
    """Sections and pages this user's role can open."""
    out = []
    for title, items in NAV:
        pages = [{"id": i, "label": label, "path": path, "icon": icon, "capability": cap}
                 for i, label, path, icon, cap in items if security.can(user, cap)]
        if pages:
            out.append({"title": title, "items": pages})
    return out


def public_meta() -> dict:
    return {"name": cfg.app.name, "tagline": cfg.app.get("tagline", ""), "organisation": cfg.app.get("organisation", "")}


def lookups() -> dict:
    return {
        "severities": dict(cfg.classification.severity_labels.items()),
        "categories": classify.CATEGORIES,
        "states": STATE_LABELS,
        "sources": SOURCE_LABELS,
        "windows": [{"id": w, "label": WINDOW_LABELS.get(w, w)} for w in analytics.WINDOWS],
        "roles": dict(cfg.roles.items()),
        "password_min_length": cfg.security.password_min_length,
        "diagnostics_mode": cfg.diagnostics.mode,
    }
