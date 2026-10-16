"""Every test session runs against a throw-away database and upload folder."""
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp(prefix="nocturne-test-"))
os.environ["NOCTURNE__STORAGE__DATABASE"] = str(TMP / "test.db")
os.environ["NOCTURNE__STORAGE__UPLOADS"] = str(TMP / "uploads")
os.environ["NOCTURNE_ADMIN_PASSWORD"] = "Admin#Test2026"
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.web import app
    with TestClient(app) as c:
        yield c


def login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = re.search(r'name="csrf" content="([^"]*)"', client.get("/account").text).group(1)
    client.headers["X-CSRF-Token"] = token
    return r.json()


@pytest.fixture(scope="session")
def admin(client):
    login(client, "admin", "Admin#Test2026")
    return client


def import_file(client, path: Path, options=None):
    with open(path, "rb") as fh:
        r = client.post("/api/data/uploads", files=[("files", (path.name, fh.read(), "text/csv"))])
    assert r.status_code == 200, r.text
    job = r.json()["jobs"][0]
    run = client.post(f"/api/data/jobs/{job['id']}/run", json={"dataset": job["dataset"], "mapping": job["mapping"], "options": options or {}})
    assert run.status_code == 200, run.text
    for _ in range(200):
        status = client.get(f"/api/data/jobs/{job['id']}").json()
        if status["status"] in ("succeeded", "failed", "cancelled"):
            return status
        time.sleep(0.1)
    raise AssertionError("import did not finish")


@pytest.fixture(scope="session")
def loaded(admin):
    ev = import_file(admin, SAMPLES / "events_upload_test.csv")
    tk = import_file(admin, SAMPLES / "tickets_upload_test.csv")
    assert ev["status"] == "succeeded" and tk["status"] == "succeeded", (ev["message"], tk["message"])
    return {"events": ev, "tickets": tk}
