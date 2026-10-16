"""Preliminary checks: ping, traceroute, DNS and TCP ports.

mode = "simulated": deterministic results that follow the device's last known state, always labelled as simulated.
mode = "live":      real checks from this server (no shell, validated host, hard timeouts).
"""
from __future__ import annotations

import asyncio
import hashlib
import platform
import random
import re
import socket
import time

from .. import db
from ..config import cfg

D = cfg.diagnostics
_HOST = re.compile(r"^(?:\d{1,3}(?:\.\d{1,3}){3}|[A-Za-z0-9](?:[A-Za-z0-9-]{0,62})(?:\.[A-Za-z0-9-]{1,63})*)$")
_cache: dict[tuple, tuple[float, dict]] = {}


def valid_host(host: str) -> bool:
    return bool(host) and len(host) <= 253 and bool(_HOST.match(host))


def known_host(host: str) -> bool:
    """The host is a device IP or device name in the inventory."""
    with db.session() as conn:
        return bool(db.scalar(conn, "SELECT 1 FROM devices WHERE ip=? OR name_key=? LIMIT 1", (host, host.lower())))


def _last_node_state(conn, host: str) -> str | None:
    row = db.one(conn, """SELECT e.transition FROM events e JOIN devices d ON d.id = e.device_id
                          WHERE (d.ip = ? OR d.name_key = ?) AND e.transition IS NOT NULL AND e.pair_key LIKE '%|node'
                          ORDER BY e.ts DESC, e.source_id DESC LIMIT 1""", (host, host.lower()))
    return row["transition"] if row else None


def _simulate(host: str, state: str | None) -> dict:
    seed = int(hashlib.md5(host.encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed + int(time.time() // 30))
    down = state == "down"
    octets = host.split(".") if re.match(r"^\d+(\.\d+){3}$", host) else ["10", str(seed % 250), str(seed // 7 % 250), "10"]
    base = 6 + seed % 40
    samples = [None] * D.ping_count if down else [round(base + rnd.uniform(-2, 6), 1) for _ in range(D.ping_count)]
    got = [s for s in samples if s is not None]
    hops = [{"hop": 1, "host": "10.0.0.1", "ms": round(0.8 + rnd.random(), 1)},
            {"hop": 2, "host": "10.255.0.2", "ms": round(2 + rnd.random() * 2, 1)},
            {"hop": 3, "host": f"172.{16 + seed % 15}.{seed % 200}.1", "ms": round(base * 0.6, 1)},
            {"hop": 4, "host": f"{octets[0]}.{octets[1]}.{octets[2]}.1", "ms": round(base * 0.9, 1)}]
    if down:
        hops += [{"hop": 5, "host": "*", "ms": None}, {"hop": 6, "host": "*", "ms": None}]
    else:
        hops.append({"hop": 5, "host": host, "ms": round(base + rnd.uniform(0, 3), 1)})
    ptr = db_name_for(host)
    return {
        "ping": {"reachable": not down, "sent": D.ping_count, "received": len(got),
                 "loss_pct": round(100 * (1 - len(got) / D.ping_count), 1), "avg_ms": round(sum(got) / len(got), 1) if got else None,
                 "min_ms": min(got) if got else None, "max_ms": max(got) if got else None, "samples": samples},
        "traceroute": {"completed": not down, "hops": hops,
                       "note": f"No reply after hop 4 ({hops[3]['host']}) — the site gateway answers, the device does not." if down else "Path complete."},
        "dns": {"ok": True, "forward": [host] if re.match(r"^\d", host) else [f"{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"],
                "reverse": ptr},
        "tcp": [{"port": p, "open": not down, "ms": None if down else round(base + rnd.uniform(0, 4), 1)} for p in D.tcp_ports],
    }


_names: dict[str, str] = {}


def db_name_for(host: str) -> str | None:
    if host in _names:
        return _names[host]
    if len(_names) > 5000:
        _names.clear()
    with db.session() as conn:
        row = db.one(conn, "SELECT name FROM devices WHERE ip=? OR name_key=? LIMIT 1", (host, host.lower()))
    name = (row["name"].lower() + ".corp.local") if row else None
    _names[host] = name
    return name


async def _run(cmd: list[str], timeout: float) -> tuple[str, int]:
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return out.decode(errors="replace"), proc.returncode or 0
    except asyncio.TimeoutError:
        return "timed out", -1
    except FileNotFoundError:
        return f"{cmd[0]} is not installed on this server", -2


async def _live_ping(host: str) -> dict:
    win = platform.system() == "Windows"
    cmd = ["ping", "-n" if win else "-c", str(D.ping_count), host]
    if not win:  # per-reply wait: seconds on Linux, milliseconds on macOS/BSD
        cmd[1:1] = ["-W", "2000" if platform.system() == "Darwin" else "2"]
    out, code = await _run(cmd, D.timeout_seconds + D.ping_count * 2)
    times = [float(x) for x in re.findall(r"time[=<]\s*([\d.]+)\s*ms", out)]
    received = len(times)
    return {"reachable": received > 0, "sent": D.ping_count, "received": received,
            "loss_pct": round(100 * (1 - received / D.ping_count), 1),
            "avg_ms": round(sum(times) / received, 1) if times else None, "min_ms": min(times) if times else None,
            "max_ms": max(times) if times else None, "samples": times or [None] * D.ping_count,
            "error": out.strip()[-200:] if code == -2 else None}


async def _live_traceroute(host: str) -> dict:
    win = platform.system() == "Windows"
    cmd = ["tracert", "-d", "-h", str(D.traceroute_hops), "-w", "1000", host] if win else \
          ["traceroute", "-n", "-m", str(D.traceroute_hops), "-w", "1", "-q", "1", host]
    out, code = await _run(cmd, D.timeout_seconds * 4)
    hops = []
    for line in out.splitlines():
        m = re.match(r"^\s*(\d+)\s+(.*)$", line)
        if not m:
            continue
        ip = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", m.group(2))
        ms = re.search(r"([\d.]+)\s*ms", m.group(2))
        hops.append({"hop": int(m.group(1)), "host": ip.group(1) if ip else "*", "ms": float(ms.group(1)) if ms else None})
    completed = bool(hops) and hops[-1]["host"] == host
    note = out.strip()[-160:] if code == -2 else ("Path complete." if completed else "Destination did not answer within the hop limit.")
    return {"completed": completed, "hops": hops, "note": note}


async def _live_dns(host: str) -> dict:
    loop = asyncio.get_running_loop()
    result = {"ok": False, "forward": [], "reverse": None}
    try:
        if re.match(r"^\d", host):
            name, _, _ = await asyncio.wait_for(loop.run_in_executor(None, socket.gethostbyaddr, host), D.timeout_seconds)
            result.update(ok=True, reverse=name, forward=[host])
        else:
            infos = await asyncio.wait_for(loop.getaddrinfo(host, None, family=socket.AF_INET), D.timeout_seconds)
            result.update(ok=True, forward=sorted({i[4][0] for i in infos}))
    except Exception as exc:
        result["error"] = str(exc) or type(exc).__name__
    return result


async def _live_tcp(host: str, port: int) -> dict:
    start = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=min(D.timeout_seconds, 4))
        writer.close()
        return {"port": port, "open": True, "ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception:
        return {"port": port, "open": False, "ms": None}


async def run_checks(host: str, pace: bool = True) -> dict:
    if not valid_host(host):
        raise ValueError("Enter a valid IPv4 address or host name.")
    with db.session() as conn:
        state = _last_node_state(conn, host)
    key = (host, state, D.mode)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < D.cache_seconds:
        return {**hit[1], "cached": True}
    started = time.perf_counter()
    if D.mode == "live":
        ping, trace, dns, *tcp = await asyncio.gather(_live_ping(host), _live_traceroute(host), _live_dns(host),
                                                       *[_live_tcp(host, p) for p in D.tcp_ports])
        result = {"ping": ping, "traceroute": trace, "dns": dns, "tcp": tcp}
    else:
        if pace:
            await asyncio.sleep(0.6)  # keep the UI's check sequence perceptible
        result = _simulate(host, state)
    p = result["ping"]
    verdict = ("Reachable" if p["reachable"] else "Unreachable") + (f", {p['avg_ms']} ms average" if p.get("avg_ms") else "")
    result.update({"host": host, "mode": D.mode, "simulated": D.mode != "live", "verdict": verdict,
                   "known_state": state, "ran_at": db.now(), "duration_ms": round((time.perf_counter() - started) * 1000)})
    if len(_cache) > 1000:  # bound memory: drop expired results
        for k in [k for k, (at, _) in _cache.items() if time.time() - at >= D.cache_seconds]:
            _cache.pop(k, None)
    _cache[key] = (time.time(), result)
    return result
