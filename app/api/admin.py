"""User management, audit trail and the read-only effective configuration."""
from __future__ import annotations

import platform
import sys

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import config, db, security
from ..bus import bus
from ..cache import cache
from ..config import cfg
from ..security import client_ip, require
from ..services import ai

router = APIRouter(prefix="/api/admin", tags=["admin"])


class NewUser(BaseModel):
    username: str
    display_name: str | None = None
    role: str
    password: str


class UserEdit(BaseModel):
    display_name: str | None = None
    role: str | None = None
    active: bool | None = None


class Reset(BaseModel):
    password: str


@router.get("/users")
def users(user=Depends(require("manage_users")), conn=Depends(db.get_conn)):
    return {"users": db.rows(conn, "SELECT id, username, display_name, role, active, must_change, created_at, last_login_at "
                                   "FROM users ORDER BY username COLLATE NOCASE"),
            "roles": dict(cfg.roles.items()),
            "permissions": {cap: list(roles) for cap, roles in cfg.permissions.items()}}


@router.post("/users")
def create_user(body: NewUser, request: Request, user=Depends(require("manage_users")), conn=Depends(db.get_conn)):
    name = body.username.strip()
    if not name or len(name) > 64 or not name.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "Usernames use letters, digits, dots, dashes or underscores (up to 64).")
    if body.role not in cfg.roles:
        raise HTTPException(400, "Unknown role.")
    problem = security.password_problem(body.password)
    if problem:
        raise HTTPException(400, problem)
    if db.one(conn, "SELECT 1 FROM users WHERE username=?", (name,)):
        raise HTTPException(409, "That username is taken.")
    conn.execute("INSERT INTO users(username, display_name, password_hash, role, must_change, created_at) VALUES (?,?,?,?,1,?)",
                 (name, (body.display_name or name).strip(), security.hash_password(body.password), body.role, db.now()))
    db.audit(conn, user, "user.create", name, body.role, client_ip(request))
    return {"ok": True}


@router.patch("/users/{user_id}")
def edit_user(user_id: int, body: UserEdit, request: Request, user=Depends(require("manage_users")), conn=Depends(db.get_conn)):
    target = db.one(conn, "SELECT * FROM users WHERE id=?", (user_id,))
    if not target:
        raise HTTPException(404, "User not found.")
    if body.role is not None and body.role not in cfg.roles:
        raise HTTPException(400, "Unknown role.")
    demoting = (body.role and body.role != "admin") or body.active is False
    if target["role"] == "admin" and target["active"] and demoting:
        admins = db.scalar(conn, "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1", default=0)
        if admins <= 1:
            raise HTTPException(400, "Keep at least one active administrator.")
    conn.execute("UPDATE users SET display_name=COALESCE(?, display_name), role=COALESCE(?, role), active=COALESCE(?, active) WHERE id=?",
                 (body.display_name, body.role, None if body.active is None else int(body.active), user_id))
    if body.active is False:
        security.revoke_sessions(conn, user_id)
    db.audit(conn, user, "user.update", target["username"], body.model_dump_json(exclude_none=True), client_ip(request))
    return {"ok": True}


@router.post("/users/{user_id}/reset")
def reset_password(user_id: int, body: Reset, request: Request, user=Depends(require("manage_users")), conn=Depends(db.get_conn)):
    target = db.one(conn, "SELECT username FROM users WHERE id=?", (user_id,))
    if not target:
        raise HTTPException(404, "User not found.")
    problem = security.password_problem(body.password)
    if problem:
        raise HTTPException(400, problem)
    conn.execute("UPDATE users SET password_hash=?, must_change=1 WHERE id=?", (security.hash_password(body.password), user_id))
    security.revoke_sessions(conn, user_id)
    db.audit(conn, user, "user.password_reset", target["username"], ip=client_ip(request))
    return {"ok": True}


@router.get("/audit")
def audit(q: str = "", page: int = 1, size: int = 50, user=Depends(require("view_audit")), conn=Depends(db.get_conn)):
    size, page = max(1, min(size, 200)), max(page, 1)
    where, params = "1=1", []
    if q:
        where = "(username LIKE ? OR action LIKE ? OR target LIKE ? OR detail LIKE ?)"
        params = [f"%{q}%"] * 4
    total = db.scalar(conn, f"SELECT COUNT(*) FROM audit_log WHERE {where}", params, 0)
    items = db.rows(conn, f"SELECT * FROM audit_log WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                    params + [size, (page - 1) * size])
    actions = db.rows(conn, "SELECT action, COUNT(*) n FROM audit_log GROUP BY action ORDER BY n DESC LIMIT 12")
    return {"items": items, "total": total, "page": page, "size": size, "actions": actions}


@router.get("/settings")
def settings(user=Depends(require("view_settings")), conn=Depends(db.get_conn)):
    return {
        "config": config.masked_view(),
        "config_path": str(config.CONFIG_PATH),
        "system": {"python": sys.version.split()[0], "platform": platform.platform(), "sqlite": db.scalar(conn, "SELECT sqlite_version()"),
                   "live_listeners": bus.listeners, "ai_configured": ai.configured(), "ai_mode": cfg.ai.mode,
                   "data_version": db.data_version(conn), **{f"query_cache_{k}": v for k, v in cache.stats().items()}, **ai.stats(conn)},
    }
