from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db, navigation, security
from ..security import current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Login(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current: str
    new: str


@router.post("/login")
def login(body: Login, request: Request, conn=Depends(db.get_conn)):
    username, ip = body.username.strip(), security.client_ip(request)
    if security.throttled(username, ip):
        db.audit(conn, {"username": username}, "auth.login_throttled", username, ip=ip)
        conn.commit()  # the HTTP error below skips the dependency's commit
        raise HTTPException(429, "Too many attempts. Wait a few minutes, then try again.")
    user = db.one(conn, "SELECT * FROM users WHERE username=?", (username,))
    if not security.verify_login(body.password, user) or not user["active"]:
        security.record_failure(username, ip)
        db.audit(conn, {"username": username}, "auth.login_failed", username, ip=ip)
        conn.commit()  # the HTTP error below skips the dependency's commit
        raise HTTPException(401, "That username and password don't match an active account.")
    security.clear_failures(username, ip)
    security.start_session(conn, request, user)
    conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (db.now(), user["id"]))
    db.audit(conn, user, "auth.login", username, ip=security.client_ip(request))
    return {"ok": True, "must_change": bool(user["must_change"]), "csrf": request.session["csrf"]}


@router.post("/logout")
def logout(request: Request, conn=Depends(db.get_conn)):
    user = security.session_user(request)
    if user:
        db.audit(conn, user, "auth.logout", user["username"], ip=security.client_ip(request))
    security.end_session(conn, request)
    return {"ok": True}


@router.get("/me")
def me(request: Request, user=Depends(current_user)):
    """The signed-in person, their CSRF token, the pages their role can open and the UI lookups."""
    return {**user, "csrf": request.session.get("csrf", ""), "nav": navigation.nav_for(user), "lookups": navigation.lookups()}


@router.post("/password")
def change_password(body: PasswordChange, request: Request, user=Depends(current_user), conn=Depends(db.get_conn)):
    row = db.one(conn, "SELECT password_hash FROM users WHERE id=?", (user["id"],))
    if not security.verify_password(body.current, row["password_hash"]):
        raise HTTPException(400, "Your current password is not correct.")
    problem = security.password_problem(body.new)
    if problem:
        raise HTTPException(400, problem)
    if body.new == body.current:
        raise HTTPException(400, "Choose a password different from the current one.")
    conn.execute("UPDATE users SET password_hash=?, must_change=0 WHERE id=?", (security.hash_password(body.new), user["id"]))
    security.revoke_sessions(conn, user["id"], keep=request.session.get("sid"))  # sign out every other device
    db.audit(conn, user, "auth.password_changed", user["username"], ip=security.client_ip(request))
    return {"ok": True}
