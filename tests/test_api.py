import io

from conftest import SAMPLES, import_file, login


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_requires_login(client):
    fresh = client.__class__(client.app)
    assert fresh.get("/api/alerts").status_code == 401
    assert fresh.get("/", follow_redirects=False).status_code == 303


def test_import_quality(loaded):
    ev = loaded["events"]["stats"]
    assert ev["stats"]["events_in_file"] == 15
    assert ev["dates"]["last"][:10] == "2026-10-09" and ev["dates"]["format"].startswith("day-first")
    assert ev["sites"]["site_column_trusted"] is True
    tk = loaded["tickets"]["stats"]
    assert tk["linking"]["tickets_linked"] == 7
    assert tk["linking"]["time_evidence"]["confirmed"] >= 1  # sample tickets open minutes after their alerts


def test_reimport_is_idempotent(admin, loaded):
    again = import_file(admin, SAMPLES / "events_upload_test.csv")
    st = again["stats"]["stats"]
    assert st["events_unchanged"] == 15 and st["events_updated"] == 0 and st["events_inserted"] == 0


def test_ticket_versions_and_reupload(admin, loaded, tmp_path):
    import csv
    src = list(csv.reader(open(SAMPLES / "tickets_upload_test.csv", encoding="utf-8-sig")))
    head, rows = src[0], src[1:]
    col = {h: i for i, h in enumerate(head)}
    same = import_file(admin, SAMPLES / "tickets_upload_test.csv")["stats"]["stats"]
    assert same["tickets_unchanged"] == len(rows) and same["tickets_updated"] == 0

    newer = [list(r) for r in rows if r[col["number"]] == "INC0095002"][0]
    newer[col["state"]], newer[col["sys_updated_on"]], newer[col["closed_at"]] = "Closed", "10-09-2026 11:00", "10-09-2026 11:00"
    path = tmp_path / "tickets_newer.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([head, newer])
    job = import_file(admin, path)["stats"]
    assert job["stats"]["tickets_updated"] == 1 and job["state_changes"] == {"Open → Closed": 1}

    old = import_file(admin, SAMPLES / "tickets_upload_test.csv")["stats"]["stats"]
    assert old["tickets_skipped_older"] == 1  # the stale export does not reopen INC0095002
    assert admin.get("/api/tickets/INC0095002").json()["ticket"]["state"] == "Closed"


def test_alert_search_and_facets(admin, loaded):
    r = admin.get("/api/alerts", params={"q": "dallas", "actionable": ""}).json()
    assert r["total"] >= 2 and all("Dallas" in i["device_name"] for i in r["items"])
    assert admin.get("/api/alerts", params={"q": "10.201.10.1", "actionable": ""}).json()["total"] >= 2
    assert admin.get("/api/alerts", params={"q": "0412", "actionable": ""}).json()["total"] >= 2
    assert set(r["facets"]) == {"severity", "category", "state", "source"}


def test_triage_pipeline(admin, loaded):
    item = admin.get("/api/alerts", params={"q": "Dallas", "severity": "P1"}).json()["items"][0]
    a = admin.get(f"/api/alerts/{item['id']}/analysis").json()
    assert a["outage"]["minutes"] is not None  # Node Down pairs with the later Node Up
    h = admin.get(f"/api/alerts/{item['id']}/history").json()["tickets"]
    assert h[0]["number"] == "INC0095001" and h[0]["score"] >= 80
    assert admin.post(f"/api/alerts/{item['id']}/checks").json()["simulated"] is True
    rec = admin.get(f"/api/alerts/{item['id']}/recommendation").json()
    assert rec["steps"] and "INC0095001" in rec["based_on"]


def test_custom_alert_and_catalog(admin, loaded):
    r = admin.post("/api/sim/custom", json={"device_name": "0777-Testtown-OH-SW01", "type_id": 1, "message": "{device} has stopped responding"})
    e = r.json()["created"][0]
    assert e["severity"] == "P1" and e["site_code"] == "0777" and e["source"] == "custom"
    r = admin.put("/api/data/catalog/1", json={"name": "Node Down", "severity": "P2", "category": None})
    assert r.status_code == 200
    assert admin.get(f"/api/alerts/{e['id']}").json()["event"]["severity"] == "P2"
    admin.put("/api/data/catalog/1", json={"name": None, "severity": None, "category": None})


def test_role_permissions(admin, client):
    admin.post("/api/admin/users", json={"username": "ana", "role": "user", "password": "Analyst#2026x"})
    analyst = client.__class__(client.app)
    assert login(analyst, "ana", "Analyst#2026x")["must_change"] is True
    assert analyst.get("/api/alerts").status_code == 403  # must change password first
    assert analyst.post("/api/auth/password", json={"current": "Analyst#2026x", "new": "Analyst#2026y"}).status_code == 200
    assert analyst.get("/api/alerts").status_code == 200
    for path in ("/api/data/jobs", "/api/admin/users", "/api/sim/options"):
        assert analyst.get(path).status_code == 403
    analyst.headers.pop("X-CSRF-Token")
    assert analyst.post("/api/alerts/1/state", json={"state": "acknowledged"}).status_code == 403


def test_diagnostics_rejects_injection(admin):
    assert admin.post("/api/diagnostics", json={"host": "10.0.0.1;reboot"}).status_code == 400


def test_xlsx_upload(admin):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["number", "state", "sys_created_on", "short_description"])
    ws.append(["INC9999999", "Closed", "10-09-2026 10:00", "Switch 0412-Dallas-TX-CoreSW-01 replaced PSU"])
    buf = io.BytesIO(); wb.save(buf)
    r = admin.post("/api/data/uploads", files=[("files", ("t.xlsx", buf.getvalue(), "application/octet-stream"))])
    assert r.json()["jobs"][0]["dataset"] == "tickets"


def test_purge_simulated(admin, loaded):
    r = admin.post("/api/data/purge", json={"scope": "simulated", "confirm": "PURGE"})
    assert r.status_code == 200
    assert admin.get("/api/alerts", params={"source": "custom,simulation", "actionable": ""}).json()["total"] == 0


def test_event_timestamps_are_checked(admin, tmp_path):
    head = "EventID,EventTime,EventType,Message,DeviceName\n"
    good = tmp_path / "events_checked.csv"
    good.write_text(head + "900000001,27-09-2026 10:00,1,Node Down,0412-Dallas-TX-AP01\n"
                           "900000002,,1,Node Down,0412-Dallas-TX-AP02\n"
                           "900000003,31-02-2026 10:00,1,Node Down,0412-Dallas-TX-AP03\n"
                           "900000004,10:00:00,1,Node Down,0412-Dallas-TX-AP04\n", encoding="utf-8")
    job = import_file(admin, good)
    assert job["status"] == "succeeded"
    assert job["stats"]["stats"]["events_in_file"] == 1
    assert set(job["stats"]["reject_reasons"]) == {"Missing timestamp", "Invalid date: 31-02-2026 10:00", "Time without a date: 10:00:00"}
    time_only = tmp_path / "events_time_only.csv"
    time_only.write_text(head + "".join(f"90000010{i},10:0{i}:00,1,Node Down,0412-Dallas-TX-AP0{i}\n" for i in range(5)), encoding="utf-8")
    job = import_file(admin, time_only)
    assert job["status"] == "failed" and "full date and time" in job["message"]


def test_resync_matches_import(admin, loaded):
    r = admin.post("/api/data/resync").json()
    assert r["linking"]["tickets_linked"] == 7 and r["events"]["count"] >= 15


def test_stated_start_is_validated(admin, loaded, tmp_path):
    path = tmp_path / "tickets_start.csv"
    path.write_text("number,state,sys_created_on,short_description\n"
                    "INC0099901,Open,10-09-2026 10:00,Switch down | Start time: 10/09/2026 09:20 AM\n"
                    "INC0099902,Open,10-09-2026 10:00,Switch down | Start time: 10/09/2026 03:20 PM\n", encoding="utf-8")
    st = import_file(admin, path)["stats"]["stats"]
    assert st["stated_start_times_used"] == 1 and st["stated_start_times_ignored"] == 1  # 5 h after opening = typo / other zone
    assert admin.get("/api/tickets/INC0099901").json()["ticket"]["incident_start"] == "2026-10-09 09:20:00"
    assert admin.get("/api/tickets/INC0099902").json()["ticket"]["incident_start"] is None
