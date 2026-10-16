"""Passwords, sessions, CSRF and role-based permissions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request

from . import db
from .config import cfg, secret

# ── password hashing (scrypt, stdlib only) ───────────────────────────────────

_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        salt, digest = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
    except ValueError:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=len(digest))
    return hmac.compare_digest(candidate, digest)


def password_problem(password: str) -> str | None:
    if len(password) < cfg.security.password_min_length:
        return f"Use at least {cfg.security.password_min_length} characters."
    classes = sum([any(c.islower() for c in password), any(c.isupper() for c in password),
                   any(c.isdigit() for c in password), any(not c.isalnum() for c in password)])
    if classes < 3:
        return "Mix at least three of: lowercase, uppercase, digits, symbols."
    return None


# ── login throttling ─────────────────────────────────────────────────────────
# Failures count per username *and* client address, so nobody can lock a colleague out from elsewhere,
# plus a wider per-address budget that stops one client from guessing across many usernames.

_failures: dict[str, list[float]] = {}
_fail_lock = threading.Lock()
_DUMMY_HASH = None  # verified against for unknown usernames so response times do not reveal which accounts exist


def _keys(username: str, ip: str) -> tuple[str, str]:
    return f"u:{username.lower()}|{ip}", f"ip:{ip}"


def _recent(key: str, window: float) -> list[float]:
    recent = [t for t in _failures.get(key, []) if time.time() - t < window]
    if recent:
        _failures[key] = recent
    else:
        _failures.pop(key, None)
    return recent


def throttled(username: str, ip: str = "") -> bool:
    window = cfg.security.login_lockout_minutes * 60
    user_key, ip_key = _keys(username, ip)
    with _fail_lock:
        return (len(_recent(user_key, window)) >= cfg.security.login_max_attempts
                or len(_recent(ip_key, window)) >= cfg.security.login_max_attempts * cfg.security.login_ip_multiplier)


def record_failure(username: str, ip: str = "") -> None:
    with _fail_lock:
        if len(_failures) > 10000:  # bound memory: drop entries whose window has passed
            window = cfg.security.login_lockout_minutes * 60
            for key in list(_failures):
                _recent(key, window)
        for key in _keys(username, ip):
            _failures.setdefault(key, []).append(time.time())


def clear_failures(username: str, ip: str = "") -> None:
    with _fail_lock:
        _failures.pop(_keys(username, ip)[0], None)


def verify_login(password: str, user: dict | None) -> bool:
    """Password check that costs the same whether or not the account exists."""
    global _DUMMY_HASH
    if user is None:
        _DUMMY_HASH = _DUMMY_HASH or hash_password(secrets.token_urlsafe(16))
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, user["password_hash"])


# ── bootstrap ────────────────────────────────────────────────────────────────

DEFAULT_ADMIN_PASSWORD = "ChangeMe@2026"


def ensure_admin() -> str | None:
    """Create the first administrator. Returns the password when a default one was used."""
    with db.session() as conn:
        if db.scalar(conn, "SELECT COUNT(*) FROM users", default=0):
            return None
        env_password = secret(cfg.security.admin_password_env)
        password = env_password or DEFAULT_ADMIN_PASSWORD
        conn.execute(
            "INSERT INTO users(username, display_name, password_hash, role, must_change, created_at) VALUES (?,?,?,?,?,?)",
            (cfg.security.admin_username, "Administrator", hash_password(password), "admin",
             0 if env_password else 1, db.now()),
        )
        db.audit(conn, None, "user.bootstrap", cfg.security.admin_username)
        return None if env_password else password


# ── session helpers ──────────────────────────────────────────────────────────

# Sessions are recorded server-side: the signed cookie only carries an opaque id, so signing out, changing a
# password or an administrator's reset/disable ends sessions immediately instead of at cookie expiry.

def start_session(conn, request: Request, user: dict) -> None:
    sid = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=cfg.security.session_hours)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (db.now(),))
    conn.execute("INSERT INTO sessions(id, user_id, created_at, expires_at, ip) VALUES (?,?,?,?,?)",
                 (sid, user["id"], db.now(), expires.strftime("%Y-%m-%d %H:%M:%S"), client_ip(request)))
    request.session.clear()
    request.session.update({"sid": sid, "csrf": secrets.token_urlsafe(24), "exp": expires.timestamp()})


def end_session(conn, request: Request) -> None:
    sid = request.session.get("sid")
    if sid:
        conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    request.session.clear()


def revoke_sessions(conn, user_id: int, keep: str | None = None) -> None:
    """End every session of a user, optionally keeping the one making the request."""
    conn.execute("DELETE FROM sessions WHERE user_id=? AND id IS NOT ?", (user_id, keep))


def session_user(request: Request) -> dict | None:
    sid, exp = request.session.get("sid"), request.session.get("exp", 0)
    if not sid or exp < time.time():
        return None
    with db.session() as conn:
        user = db.one(conn, """SELECT u.id, u.username, u.display_name, u.role, u.active, u.must_change FROM sessions s
                               JOIN users u ON u.id = s.user_id WHERE s.id=? AND s.expires_at >= ?""", (sid, db.now()))
    if not user or not user["active"]:
        return None
    user["permissions"] = sorted(perms_for(user["role"]))
    user["role_label"] = cfg.roles.get(user["role"], user["role"])
    return user


def perms_for(role: str) -> set[str]:
    return {cap for cap, roles in cfg.permissions.items() if role in roles}


def can(user: dict | None, capability: str) -> bool:
    return bool(user) and user["role"] in cfg.permissions.get(capability, [])


# ── FastAPI dependencies ─────────────────────────────────────────────────────

def current_user(request: Request) -> dict:
    user = session_user(request)
    if not user:
        raise HTTPException(401, "Sign in to continue.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        token = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(token, request.session.get("csrf", "")):
            raise HTTPException(403, "Security token missing or expired. Reload the page and try again.")
    return user


def require(capability: str):
    def checker(user: dict = Depends(current_user)) -> dict:
        if not can(user, capability):
            raise HTTPException(403, "Your role does not allow this action.")
        if user["must_change"] and capability != "__password__":
            raise HTTPException(403, "Change your password before continuing.")
        return user
    return checker


def client_ip(request: Request) -> str:
    # X-Forwarded-For is not read here: uvicorn (proxy_headers) applies it only for trusted proxies
    # (--forwarded-allow-ips), so a client cannot forge the address recorded in the audit trail.
    return request.client.host if request.client else ""
