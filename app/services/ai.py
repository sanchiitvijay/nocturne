"""Gemini intelligence, grounded in this alert's evidence and similar past incidents.

Efficiency rules:
  * Answers are cached in the database under a fingerprint of the evidence (alert, signals, matched tickets,
    check verdict). Re-opening the same alert costs nothing; changed evidence produces a fresh answer.
  * Identical requests in flight share one provider call.
  * The built-in engine always produces a plan, so a provider failure degrades to a labelled fallback.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from .. import db
from ..config import cfg, secret

A = cfg.ai
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
CONFIDENCE = {"high": 85, "medium": 65, "low": 40}


class AIUnavailable(Exception):
    """Raised with a reason an analyst can read ("AI key not set", "provider timed out", …)."""


def configured() -> bool:
    return bool(A.enabled and A.mode != "off" and secret(A.api_key_env))


def status() -> dict:
    return {"enabled": bool(A.enabled), "mode": A.mode, "configured": configured(), "model": A.model,
            "provider": A.provider, "auto_severities": list(A.auto_severities)}


def wants_auto(event: dict) -> bool:
    """AI is expected for this alert (a missing key then shows as a labelled fallback, not silently)."""
    return bool(A.enabled) and A.mode == "auto" and event.get("severity") in A.auto_severities


def label() -> str:
    words = A.model.replace(A.provider + "-", "").split("-")
    return " ".join([A.provider.title()] + [w if w[:1].isdigit() else w.title() for w in words])


# ── context & fingerprint ─────────────────────────────────────────────────────

def context(event: dict, device: dict | None, site: dict | None, analysis: dict, history: list[dict],
            checks: dict | None, engine: dict) -> dict:
    ping = (checks or {}).get("ping") or {}
    return {
        "alert": {k: event.get(k) for k in ("id", "ts", "name", "message", "severity", "category", "transition", "status_label")},
        "device": {k: (device or {}).get(k) for k in ("name", "ip", "role", "machine_type", "vendor")},
        "site": {"code": event.get("site_code"), "label": (site or {}).get("label")},
        "evidence": [s["text"] for s in engine["signals"]],
        "outage": {k: (analysis.get("outage") or {}).get(k) for k in ("down_ts", "up_ts", "minutes")},
        "recent_device_events": [f"{t['ts'][11:19] if t.get('ts') else ''} {t['name']}" for t in analysis.get("timeline", [])[-12:]],
        "checks": {"mode": (checks or {}).get("mode"), "reachable": ping.get("reachable"), "loss_pct": ping.get("loss_pct"),
                   "traceroute_completed": ((checks or {}).get("traceroute") or {}).get("completed")} if checks else None,
        "similar_incidents": [{"ticket": h["number"], "match_pct": h["score"], "summary": h["short_description"],
                               "what_fixed_it": h["resolution"], "state": h["state"]} for h in history[:5]],
        "engine_hypothesis": engine["hypothesis"],
    }


def fingerprint(ctx: dict) -> str:
    stable = {**ctx, "checks": {k: v for k, v in (ctx.get("checks") or {}).items() if k != "loss_pct"}}
    raw = json.dumps(stable, sort_keys=True, default=str) + A.model
    return hashlib.sha1(raw.encode()).hexdigest()


def _prompt(ctx: dict) -> str:
    return (
        "You are a senior network operations engineer helping a NOC analyst triage one alert.\n"
        "Use ONLY the evidence provided. Prefer what fixed the similar incidents when they genuinely match. "
        "Never invent devices, tickets or results. If evidence is thin, say so and lower confidence.\n"
        "Reply as JSON with keys:\n"
        '  "hypothesis": one or two sentences on the most likely root cause,\n'
        '  "steps": array of 3-7 objects {"text": concrete next action, "why": short reason},\n'
        '  "confidence": "high" | "medium" | "low",\n'
        '  "used_tickets": ticket numbers from similar_incidents you relied on (may be empty),\n'
        '  "watch_outs": array of short cautions (may be empty).\n\n'
        "EVIDENCE:\n" + json.dumps(ctx, default=str)[:14000]
    )


def _call_gemini(prompt: str) -> dict:
    url = A.endpoint.format(model=A.model)
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": secret(A.api_key_env) or ""})
    with urllib.request.urlopen(req, timeout=A.timeout_seconds) as resp:
        data = json.loads(resp.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    return json.loads(text)


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _normalise(parsed: dict, ctx: dict) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError("reply is not a JSON object")
    known = {i["ticket"] for i in ctx["similar_incidents"]}
    steps = []
    for s in _list(parsed.get("steps"))[:8]:
        if isinstance(s, dict) and s.get("text"):
            steps.append({"text": str(s["text"]), "why": str(s.get("why") or "")})
        elif isinstance(s, str):
            steps.append({"text": s, "why": ""})
    level = str(parsed.get("confidence", "medium")).lower()
    return {
        "hypothesis": str(parsed.get("hypothesis", "")).strip(),
        "steps": steps,
        "confidence_level": level if level in CONFIDENCE else "medium",
        "used_tickets": [t for t in _list(parsed.get("used_tickets")) if isinstance(t, str) and t in known],  # only real, provided tickets
        "watch_outs": [str(w) for w in _list(parsed.get("watch_outs"))][:5],
    }


# ── cached generation ─────────────────────────────────────────────────────────

def insight(conn, ctx: dict, force: bool = False) -> dict:
    """Return {payload, cache} for this evidence, calling the provider only when needed."""
    if not A.enabled or A.mode == "off":
        raise AIUnavailable("AI is switched off in nocturne.toml")
    if not secret(A.api_key_env):
        raise AIUnavailable(f"AI key not set ({A.api_key_env})")
    key = fingerprint(ctx)
    event_id = ctx["alert"]["id"]
    with _locks_guard:
        if len(_locks) > 512:  # bound memory: forget locks nobody holds
            for k in [k for k, l in _locks.items() if not l.locked()]:
                _locks.pop(k, None)
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        row = db.one(conn, "SELECT * FROM ai_insights WHERE cache_key=?", (key,))
        fresh_enough = row and datetime.now() - datetime.fromisoformat(row["created_at"]) < timedelta(hours=A.cache_hours)
        if row and fresh_enough and not force:
            conn.execute("UPDATE ai_insights SET hits=hits+1, last_hit_at=? WHERE cache_key=?", (db.now(), key))
            conn.commit()
            return {"payload": json.loads(row["payload"]),
                    "cache": {"cached": True, "generated_at": row["created_at"], "hits": row["hits"] + 1,
                              "age_seconds": int((datetime.now() - datetime.fromisoformat(row["created_at"])).total_seconds()),
                              "latency_ms": row["latency_ms"], "key": key[:10]}}
        started = time.perf_counter()
        try:
            payload = _normalise(_call_gemini(_prompt(ctx)), ctx)
        except urllib.error.HTTPError as exc:
            reason = {400: "the request was rejected (check the model name)", 401: "the API key was refused",
                      403: "the API key is not allowed to use this model", 429: "the provider's rate limit was hit"}
            raise AIUnavailable(f"Gemini: {reason.get(exc.code, f'HTTP {exc.code}')}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AIUnavailable("Gemini could not be reached from this server") from exc
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
            raise AIUnavailable("Gemini replied in an unexpected format") from exc
        latency = int((time.perf_counter() - started) * 1000)
        if not payload["hypothesis"]:
            raise AIUnavailable("Gemini returned an empty answer")
        now = db.now()
        conn.execute("""INSERT INTO ai_insights(cache_key, event_id, model, payload, latency_ms, hits, created_at, last_hit_at)
                        VALUES (?,?,?,?,?,0,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,
                        latency_ms=excluded.latency_ms, created_at=excluded.created_at, hits=0, last_hit_at=excluded.last_hit_at""",
                     (key, event_id, A.model, json.dumps(payload), latency, now, now))
        conn.commit()
        return {"payload": payload, "cache": {"cached": False, "generated_at": now, "age_seconds": 0, "hits": 0, "latency_ms": latency, "key": key[:10]}}


def merge(engine: dict, ai: dict, cache: dict, refreshed: bool) -> dict:
    """AI answer on top, engine evidence and proven fixes kept, every part labelled with where it came from."""
    p = ai
    steps = [s for s in engine["steps"] if s["source"] == "dedupe"]
    steps += [{"text": s["text"], "why": s["why"], "source": "ai"} for s in p["steps"]]
    seen = {s["text"].lower()[:50] for s in steps}
    steps += [s for s in engine["steps"] if s["source"] not in ("playbook", "dedupe", "correlation") and s["text"].lower()[:50] not in seen]
    blended = round(0.6 * CONFIDENCE[p["confidence_level"]] + 0.4 * engine["confidence"])
    out = {**engine,
           "source": "ai", "provider": label(), "hypothesis": p["hypothesis"], "steps": steps,
           "confidence": blended, "confidence_label": "High" if blended >= 75 else "Medium" if blended >= 50 else "Low",
           "grounded_in": p["used_tickets"], "watch_outs": p["watch_outs"], "engine_view": engine["hypothesis"],
           "cache": {**cache, "refreshed": refreshed}}
    out["work_note"] = engine["work_note"].replace("[NOCTURNE triage]", f"[NOCTURNE triage, AI-assisted by {label()}]").replace(
        f"Hypothesis: {engine['hypothesis']}", f"Hypothesis: {p['hypothesis']}")
    return out


def stats(conn) -> dict:
    r = db.one(conn, "SELECT COUNT(*) n, COALESCE(SUM(hits),0) hits, CAST(AVG(latency_ms) AS INTEGER) ms FROM ai_insights") or {}
    return {"cached_answers": r.get("n", 0), "cache_hits": r.get("hits", 0), "avg_latency_ms": r.get("ms")}
