"""Regressions for defects found in review: sessions, audit, throttling, ETL edge cases, simulator races, input checks."""
import csv
import re
import threading

from conftest import SAMPLES, import_file, login


def fresh(client):
    return client.__class__(client.app, raise_server_exceptions=False)


def signed_in(client, username, password):
    c = fresh(client)
    login(c, username, password)
    return c


def make_user(admin, username, password="Analyst#2026x", role="user"):
    r = admin.post("/api/admin/users", json={"username": username, "role": role, "password": password})
    assert r.status_code == 200, r.text
    return [u for u in admin.get("/api/admin/users").json()["users"] if u["username"] == username][0]["id"]


def change_first_password(c, current, new):
    assert c.post("/api/auth/password", json={"current": current, "new": new}).status_code == 200


# ── sessions ──────────────────────────────────────────────────────────────────

def test_logout_revokes_the_session_cookie(admin):
    c = signed_in(admin, "admin", "Admin#Test2026")
    copied = dict(c.cookies)
    assert c.post("/api/auth/logout").status_code == 200
    replay = fresh(admin)
    replay.cookies.update(copied)
    assert replay.get("/api/auth/me").status_code == 401


def test_password_change_and_reset_end_other_sessions(admin):
    uid = make_user(admin, "sess.user")
    a = signed_in(admin, "sess.user", "Analyst#2026x")
    b = signed_in(admin, "sess.user", "Analyst#2026x")
    change_first_password(a, "Analyst#2026x", "Analyst#2027y")
    assert a.get("/api/auth/me").status_code == 200       # the device that changed it stays signed in
    assert b.get("/api/auth/me").status_code == 401       # every other device is signed out
    assert admin.post(f"/api/admin/users/{uid}/reset", json={"password": "Analyst#2028z"}).status_code == 200
    assert a.get("/api/auth/me").status_code == 401


def test_disabling_a_user_ends_their_sessions(admin):
    uid = make_user(admin, "sess.off")
    c = signed_in(admin, "sess.off", "Analyst#2026x")
    assert admin.patch(f"/api/admin/users/{uid}", json={"active": False}).status_code == 200
    assert c.get("/api/auth/me").status_code == 401


# ── audit and throttling ──────────────────────────────────────────────────────

def test_failed_login_is_audited(admin):
    fresh(admin).post("/api/auth/login", json={"username": "no.such.user", "password": "wrong"})
    items = admin.get("/api/admin/audit", params={"q": "no.such.user"}).json()["items"]
    assert any(i["action"] == "auth.login_failed" for i in items)


def test_lockout_is_per_username_and_address():
    from app import security
    for _ in range(5):
        security.record_failure("victim", "6.6.6.6")
    assert security.throttled("victim", "6.6.6.6")           # the guessing client is locked out
    assert not security.throttled("victim", "10.0.0.5")      # the real user elsewhere is not
    for i in range(20):
        security.record_failure(f"spray{i}", "7.7.7.7")
    assert security.throttled("anyone", "7.7.7.7")           # spraying many usernames from one address is capped
    security._failures.clear()


def test_forwarded_for_is_not_trusted_for_audit(admin):
    fresh(admin).post("/api/auth/login", json={"username": "xff.probe", "password": "x"}, headers={"X-Forwarded-For": "6.6.6.6"})
    ips = {i["ip"] for i in admin.get("/api/admin/audit", params={"q": "xff.probe"}).json()["items"]}
    assert ips and "6.6.6.6" not in ips


def test_audit_page_size_is_bounded(admin):
    r = admin.get("/api/admin/audit", params={"size": -1}).json()
    assert len(r["items"]) <= 1 and r["size"] == 1


# ── admin rules ───────────────────────────────────────────────────────────────

def test_an_inactive_admin_can_be_demoted(admin):
    uid = make_user(admin, "adm.spare", "Admin2#Test2026", role="admin")
    assert admin.patch(f"/api/admin/users/{uid}", json={"active": False}).status_code == 200
    assert admin.patch(f"/api/admin/users/{uid}", json={"role": "user"}).status_code == 200


# ── API docs and headers ──────────────────────────────────────────────────────

def test_api_docs_need_a_session(admin):
    anon = fresh(admin)
    assert anon.get("/api/openapi.json").status_code == 401
    assert anon.get("/api/docs").status_code == 401
    assert admin.get("/api/openapi.json").json()["info"]["title"].endswith("API")
    assert "frame-ancestors 'none'" in admin.get("/api/health").headers["content-security-policy"]


# ── input validation ──────────────────────────────────────────────────────────

def test_bad_filter_values_are_400_not_500(admin, loaded):
    for params in ({"device_id": "abc"}, {"type_id": "1.5"}, {"window": "custom", "from": "garbage"}):
        r = admin.get("/api/alerts", params=params)
        assert r.status_code == 400 and r.json()["error"], params
    r = admin.get("/api/insights/overview", params={"window": "custom", "start": "garbage"})
    assert r.status_code == 400
    ok = admin.get("/api/insights/overview", params={"window": "custom", "start": "2026-10-01", "end": "2026-10-09"})
    assert ok.status_code == 200 and ok.json()["window"]["end"] == "2026-10-09 23:59:59"


def test_state_change_on_a_missing_alert_is_404(admin, loaded):
    assert admin.post("/api/alerts/999999/state", json={"state": "acknowledged"}).status_code == 404
    first = admin.get("/api/alerts", params={"actionable": ""}).json()["items"][0]["id"]
    r = admin.post("/api/alerts/bulk-state", json={"ids": [first, 999999], "state": "acknowledged"}).json()
    assert r["updated"] == 1 and r["missing"] == 1


def test_csv_export_neutralises_formulas(admin, loaded):
    admin.post("/api/sim/custom", json={"device_name": "csv-probe-01", "name": "Node Down", "message": "=HYPERLINK(\"http://x\") {device}"})
    rows = list(csv.reader(admin.get("/api/alerts/export.csv", params={"source": "custom", "actionable": ""}).text.splitlines()))
    messages = [r[rows[0].index("message")] for r in rows[1:]]
    assert any(m.startswith("'=HYPERLINK") for m in messages) and not any(m.startswith("=") for m in messages)


# ── ETL ──────────────────────────────────────────────────────────────────────

def test_cancel_only_applies_to_running_imports(admin):
    with open(SAMPLES / "events_upload_test.csv", "rb") as fh:
        job = admin.post("/api/data/uploads", files=[("files", ("cancel.csv", fh.read(), "text/csv"))]).json()["jobs"][0]
    assert admin.post(f"/api/data/jobs/{job['id']}/cancel").status_code == 409
    import time
    admin.post(f"/api/data/jobs/{job['id']}/run", json={"dataset": job["dataset"], "mapping": job["mapping"]})
    for _ in range(200):
        status = admin.get(f"/api/data/jobs/{job['id']}").json()["status"]
        if status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert status == "succeeded"


def test_events_need_a_time_of_day(admin, tmp_path):
    path = tmp_path / "date_only.csv"
    path.write_text("EventID,EventTime,EventType,Message,DeviceName\n"
                    "700000001,2026-10-01,1,Node Down,date-only-dev\n"
                    "700000002,2026-10-01 08:30,1,Node Down,date-only-dev\n")
    job = import_file(admin, path)["stats"]
    assert job["stats"]["events_in_file"] == 1
    assert list(job["reject_reasons"]) == ["Date without a time: 2026-10-01"]


def test_unversioned_ticket_row_does_not_reopen_a_closed_ticket(admin, loaded, tmp_path):
    path = tmp_path / "unversioned.csv"
    path.write_text("number,state,sys_created_on,short_description\nINC0095001,New,10-09-2026 09:15,Reopen attempt\n")
    job = import_file(admin, path)["stats"]
    assert job["stats"]["tickets_skipped_unversioned"] == 1
    assert admin.get("/api/tickets/INC0095001").json()["ticket"]["state"] == "Resolved"


# ── simulator ────────────────────────────────────────────────────────────────

def test_concurrent_custom_alerts_do_not_collide(admin, loaded):
    failures = []

    def fire():
        try:
            r = admin.post("/api/sim/custom", json={"device_name": "race-probe-01", "name": "Node Down", "message": "{device} x",
                                                    "repeat": 3, "interval_ms": 0})
            if r.status_code != 200:
                failures.append(r.text)
        except Exception as exc:  # the session client re-raises server errors inside this thread
            failures.append(repr(exc))

    threads = [threading.Thread(target=fire) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not failures
    assert admin.get("/api/devices", params={"q": "race-probe-01"}).json()["total"] == 1


def test_simulated_purge_removes_custom_devices(admin, loaded):
    admin.post("/api/sim/custom", json={"device_name": "purge-probe-01", "name": "Node Down", "message": "{device} down"})
    assert admin.get("/api/devices", params={"q": "purge-probe"}).json()["total"] == 1
    assert admin.post("/api/data/purge", json={"scope": "simulated", "confirm": "PURGE"}).status_code == 200
    assert admin.get("/api/devices", params={"q": "purge-probe"}).json()["total"] == 0
    assert admin.get("/api/devices", params={"q": "0412-Dallas"}).json()["total"] >= 1  # imported devices stay


# ── AI ──────────────────────────────────────────────────────────────────────

def test_malformed_ai_reply_is_a_labelled_fallback(monkeypatch):
    from app.services import ai
    import pytest
    monkeypatch.setattr(ai, "secret", lambda name: "test-key")
    monkeypatch.setattr(ai, "_call_gemini", lambda prompt: ["not", "an", "object"])
    ctx = {"alert": {"id": 1}, "similar_incidents": [], "checks": None}
    from app import db
    with db.session() as conn, pytest.raises(ai.AIUnavailable, match="unexpected format"):
        ai.insight(conn, ctx)
