from app.services import ai


def _first_p1(admin):
    return admin.get("/api/alerts", params={"q": "Dallas", "severity": "P1"}).json()["items"][0]


def test_fallback_is_labelled_when_ai_is_unavailable(admin, loaded):
    r = admin.post(f"/api/alerts/{_first_p1(admin)['id']}/ai", json={}).json()
    assert r["source"] == "fallback" and "key not set" in r["fallback_reason"]
    assert r["steps"]  # the built-in engine still answers


def test_ai_answer_is_cached_and_refreshable(monkeypatch, admin, loaded):
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(prompt):
        calls.append(prompt)
        return {"hypothesis": "Core switch lost power", "steps": [{"text": "Check the MDF PDU", "why": "INC0095001 pointed there"}],
                "confidence": "high", "used_tickets": ["INC0095001", "INC0000000"], "watch_outs": []}
    monkeypatch.setattr(ai, "_call_gemini", fake)
    eid = _first_p1(admin)["id"]
    first = admin.get(f"/api/alerts/{eid}/recommendation").json()       # auto mode, P1 → AI
    assert first["source"] == "ai" and first["cache"]["cached"] is False
    assert first["grounded_in"] == ["INC0095001"]                        # invented ticket numbers are dropped
    again = admin.get(f"/api/alerts/{eid}/recommendation").json()
    assert again["cache"]["cached"] is True and len(calls) == 1          # same evidence → no second provider call
    fresh = admin.post(f"/api/alerts/{eid}/ai", json={"refresh": True}).json()
    assert fresh["cache"]["refreshed"] is True and len(calls) == 2
