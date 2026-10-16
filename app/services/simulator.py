"""Alert simulation: realistic random alerts, scripted incident scenarios and custom one-off triggers.

Simulated and custom alerts are written to the same events table (source = 'simulation' / 'custom'), so every
screen, search and recommendation treats them exactly like imported alerts. They can be purged in one click.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime

from .. import db
from ..bus import bus
from ..config import cfg
from . import classify as C
from . import textmine as T

TEMPLATES = {
    "node_down": (1, "Node Down", "{device} has stopped responding (Request Timed Out)"),
    "node_up": (5, "Node Up", "{device} is responding again. Response time is {ms} milliseconds."),
    "if_down": (10, "Interface Down", "{device} - {iface} Down"),
    "if_up": (11, "Interface Up", "{device} - {iface} Up"),
    "reboot": (14, "Node Rebooted", "{device} rebooted at {stamp}"),
    "ap_gone": (604, "Thin AP Disappeared", "Thin AP {ip} disappeared from WL Controller {peer}."),
    "ups_battery": (None, "UPS On Battery", "UPS Status changed to 'On Battery' on {device}."),
    "ups_online": (6808, "UPS On Line", "UPS Status changed to 'On Line' on {device}."),
    "hw_critical": (526, "Hardware Component Critical", "Hardware type Power Supply of hardware health monitoring on {device} is Critical"),
    "hw_warning": (525, "Hardware Component Warning", "Hardware type Fan of hardware health monitoring on {device} is Warning"),
    "cpu": (None, "High CPU Utilization", "CPU load on {device} at {pct}% for over 10 minutes"),
    "loss": (5000, "Alert Triggered", "Node {device}'s packet loss has risen above 30% to {pct} %. Severity: Critical."),
    "bgp_down": (19, "Interface Status Changed", "{device} - GigabitEthernet0/0/{n} BGP WAN primary state changed to DOWN. Secondary failover active."),
    "bgp_up": (11, "Interface Up", "{device} - GigabitEthernet0/0/{n} BGP WAN primary state restored to UP. Normal routing resumed."),
}
ROLE_MENU = {
    "access point": ["node_down", "node_up", "ap_gone", "cpu"],
    "switch": ["if_down", "if_up", "node_down", "node_up", "hw_warning", "reboot", "cpu"],
    "router": ["bgp_down", "bgp_up", "loss", "node_down", "node_up"],
    "firewall": ["node_down", "node_up", "cpu", "reboot"],
    "ups": ["ups_battery", "ups_online", "node_down", "node_up"],
    "controller": ["ap_gone", "cpu", "node_down"],
}

SCENARIOS = {
    "random": {"label": "Random alerts", "text": "A realistic mix drawn from real devices and the observed event-type frequencies."},
    "site_outage": {"label": "Site outage cascade", "text": "A site's core switch drops, its APs and UPS follow within seconds, then the site recovers."},
    "flapping": {"label": "Flapping interface", "text": "One switch uplink bounces down and up several times."},
    "power": {"label": "Power event", "text": "A UPS goes on battery, hardware warns, the node drops, then power returns."},
    "wan_failover": {"label": "WAN failover", "text": "A branch router loses its primary BGP path, packet loss climbs, then the path restores."},
}


class Simulator:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.status = {"running": False, "scenario": None, "sent": 0, "total": 0, "started_by": None, "started_at": None}

    # ── event creation (sync; runs in a worker thread) ────────────────────────
    def create_event(self, spec: dict, source: str, user: dict | None = None) -> dict:
        with db.session() as conn:
            conn.execute("BEGIN IMMEDIATE")  # one writer at a time: device creation and the next source_id cannot race
            device = self._resolve_device(conn, spec)
            type_id = spec.get("type_id")
            name = spec.get("name") or C.event_name(type_id, None)
            message = (spec.get("message") or name).replace("{device}", device["name"] if device else "")
            cls = C.classify(type_id, name, message)
            if spec.get("severity") in C.SEVERITIES:
                cls["severity"] = spec["severity"]
                cls["actionable"] = int(cls["severity"] in cfg.classification.actionable_severities
                                        and cls["category"] not in cfg.classification.noise_categories)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"
            key = device["name_key"] if device else None
            status = spec.get("status_code")
            if status is None and cls["transition"]:
                status = 2 if cls["transition"] == "down" else 1
            # The next source_id is taken inside the INSERT itself, so concurrent triggers cannot pick the same one.
            cur = conn.execute(
                """INSERT INTO events(source, source_id, ts, type_id, name, message, device_id, device_name, ip,
                       site_code, status_code, severity, category, actionable, transition, pair_key, created_at, extra)
                   SELECT ?, COALESCE(MAX(source_id), 900000000) + 1, ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                   FROM events WHERE source = ?""",
                (source, ts, type_id, name, message, device["id"] if device else None, device["name"] if device else None,
                 device["ip"] if device else None, device["site_code"] if device else T.site_code(spec.get("site_code")),
                 status, cls["severity"], cls["category"], cls["actionable"], cls["transition"],
                 C.pair_key(key, name, message), db.now(), db.dumps({"scenario": spec.get("scenario"), "by": (user or {}).get("username")}),
                 source))
            event_id = cur.lastrowid
            db.fts_index_event(conn, event_id)
            if device:
                conn.execute("UPDATE devices SET last_seen=?, event_count=event_count+1, last_status=COALESCE(?, last_status) WHERE id=?",
                             (ts, status, device["id"]))
            db.bump_version(conn)
            event = db.one(conn, """SELECT e.*, s.label site_label, d.role FROM events e LEFT JOIN sites s ON s.code=e.site_code
                                    LEFT JOIN devices d ON d.id=e.device_id WHERE e.id=?""", (event_id,))
        bus.publish("alert", event)
        return event

    def _resolve_device(self, conn, spec: dict) -> dict | None:
        if spec.get("device_id"):
            return db.one(conn, "SELECT * FROM devices WHERE id=?", (spec["device_id"],))
        name = (spec.get("device_name") or "").strip()
        if not name:
            return None
        found = db.one(conn, "SELECT * FROM devices WHERE name_key=?", (name.lower(),))
        if found:
            return found
        site = T.site_code(spec.get("site_code")) or T.site_from_device(name)
        ip = T.valid_ip(spec.get("ip"))
        role = spec.get("role") or C.device_role(name)
        conn.execute("INSERT INTO devices(name, name_key, ip, site_code, role, first_seen, extra) VALUES (?,?,?,?,?,?,?)",
                     (name, name.lower(), ip, site, role, db.now(), db.dumps({"created_by": "custom alert"})))
        if site:
            lbl = T.site_label_from_device(name)
            conn.execute("INSERT INTO sites(code, label, city, state, updated_at) VALUES (?,?,?,?,?) ON CONFLICT(code) DO NOTHING",
                         (site, f"{lbl[0]}, {lbl[1]}" if lbl else None, lbl[0] if lbl else None, lbl[1] if lbl else None, db.now()))
        return db.one(conn, "SELECT * FROM devices WHERE name_key=?", (name.lower(),))

    # ── scenario planning ──────────────────────────────────────────────────────
    def plan(self, scenario: str, count: int, site: str | None = None) -> list[dict]:
        with db.session() as conn:
            if scenario == "site_outage":
                return self._plan_site(conn, site)
            if scenario == "flapping":
                dev = self._pick(conn, "switch", site)
                return self._flap(dev, max(3, min(count // 2, 8)))
            if scenario == "power":
                dev = self._pick(conn, "ups", site)
                return [self._spec(dev, k, scenario) for k in ("ups_battery", "hw_critical", "node_down", "ups_online", "node_up")]
            if scenario == "wan_failover":
                dev = self._pick(conn, "router", site)
                n = random.randint(1, 3)
                return [self._spec(dev, "bgp_down", scenario, n=n), self._spec(dev, "loss", scenario),
                        self._spec(dev, "bgp_up", scenario, n=n)]
            return self._plan_random(conn, count, site)

    def _pick(self, conn, role: str, site: str | None) -> dict:
        params = [role]
        q = "SELECT * FROM devices WHERE role=?"
        if site:
            q += " AND site_code=?"
            params.append(T.site_code(site))
        dev = db.one(conn, q + " ORDER BY RANDOM() LIMIT 1", params)
        return dev or db.one(conn, "SELECT * FROM devices ORDER BY RANDOM() LIMIT 1") or {
            "id": None, "name": f"SIM-{role.upper()}-01", "name_key": f"sim-{role}-01", "ip": "10.99.0.1", "site_code": None, "role": role}

    def _spec(self, dev: dict, template: str, scenario: str, **extra) -> dict:
        type_id, name, msg = TEMPLATES[template]
        stamp = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
        message = msg.format(device=dev["name"], ip=dev.get("ip") or "10.0.0.1", peer="WLC-CORE-01",
                             ms=random.randint(4, 90), pct=random.randint(31, 98), stamp=stamp, n=extra.get("n", 1),
                             iface=extra.get("iface") or f"Unit: 1 Slot: 0 Port: {random.randint(1, 48)} Gigabit - Level")
        return {"device_id": dev.get("id"), "device_name": dev["name"], "ip": dev.get("ip"), "site_code": dev.get("site_code"),
                "type_id": type_id, "name": name, "message": message, "scenario": scenario}

    def _flap(self, dev: dict, cycles: int) -> list[dict]:
        iface = f"Unit: 1 Slot: 0 Port: {random.randint(1, 48)} Gigabit - Level - Gi1/0/{random.randint(1, 48)}"
        out = []
        for _ in range(cycles):
            out += [self._spec(dev, "if_down", "flapping", iface=iface), self._spec(dev, "if_up", "flapping", iface=iface)]
        return out

    def _plan_site(self, conn, site: str | None) -> list[dict]:
        if not site:
            row = db.one(conn, """SELECT site_code FROM devices WHERE site_code IS NOT NULL GROUP BY site_code
                                  HAVING COUNT(*) BETWEEN 4 AND 30 ORDER BY RANDOM() LIMIT 1""")
            site = row["site_code"] if row else None
        devs = db.rows(conn, "SELECT * FROM devices WHERE site_code=? ORDER BY CASE role WHEN 'router' THEN 0 WHEN 'switch' THEN 1 "
                             "WHEN 'ups' THEN 2 ELSE 3 END LIMIT 7", (T.site_code(site),)) if site else []
        if not devs:
            return self._plan_random(conn, 6, None)
        downs = [self._spec(d, "node_down", "site_outage") for d in devs]
        ups = [self._spec(d, "node_up", "site_outage") for d in devs[:max(2, len(devs) // 2)]]
        return downs + ups

    def _plan_random(self, conn, count: int, site: str | None) -> list[dict]:
        params, q = [], "SELECT * FROM devices WHERE role IN ('access point','switch','router','firewall','ups','controller')"
        if site:
            q += " AND site_code=?"
            params.append(T.site_code(site))
        devs = db.rows(conn, q + " ORDER BY RANDOM() LIMIT 60", params) or [self._pick(conn, "switch", None)]
        out = []
        for _ in range(count):
            dev = random.choice(devs)
            out.append(self._spec(dev, random.choice(ROLE_MENU.get(dev.get("role"), ["node_down", "node_up"])), "random"))
        return out

    # ── execution ───────────────────────────────────────────────────────────────
    async def run(self, scenario: str, count: int, interval_ms: int, site: str | None, user: dict) -> dict:
        if self.task and not self.task.done():
            raise RuntimeError("A simulation is already running. Stop it first.")
        count = max(1, min(count, cfg.simulation.max_count))
        specs = await asyncio.to_thread(self.plan, scenario, count, site)
        self.status = {"running": True, "scenario": scenario, "sent": 0, "total": len(specs),
                       "started_by": user["username"], "started_at": db.now()}
        self.task = asyncio.create_task(self._stream(specs, interval_ms, user))
        bus.publish("sim", self.status)
        return self.status

    async def _stream(self, specs: list[dict], interval_ms: int, user: dict) -> None:
        try:
            for spec in specs:
                await asyncio.to_thread(self.create_event, spec, "simulation", user)
                self.status["sent"] += 1
                bus.publish("sim", self.status)
                await asyncio.sleep(max(interval_ms, 50) / 1000 * random.uniform(0.6, 1.4))
        finally:
            self.status["running"] = False
            bus.publish("sim", self.status)

    def stop(self) -> dict:
        if self.task and not self.task.done():
            self.task.cancel()
        self.status["running"] = False
        bus.publish("sim", self.status)
        return self.status


simulator = Simulator()
