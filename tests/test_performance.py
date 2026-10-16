"""Caching and transport optimisations: results stay correct after writes, compression skips the live stream."""
import asyncio


def test_cached_dashboard_and_counts_refresh_after_a_write(admin, loaded):
    before = admin.get("/api/insights/overview", params={"window": "all"}).json()["kpis"]["events"]
    count_before = admin.get("/api/alerts", params={"actionable": ""}).json()["total"]
    admin.post("/api/sim/custom", json={"device_name": "cache-probe-01", "name": "Node Down", "message": "{device} down"})
    assert admin.get("/api/insights/overview", params={"window": "all"}).json()["kpis"]["events"] == before + 1
    assert admin.get("/api/alerts", params={"actionable": ""}).json()["total"] == count_before + 1


def test_paging_reuses_the_cached_counts(admin, loaded):
    from app.cache import cache
    admin.get("/api/alerts", params={"actionable": "", "page": 1})
    hits = cache.stats()["hits"]
    second = admin.get("/api/alerts", params={"actionable": "", "page": 2, "sort": "oldest"}).json()
    assert cache.stats()["hits"] > hits and set(second["facets"]) == {"severity", "category", "state", "source"}


def test_feedback_refreshes_the_cached_ticket_ranking(admin, loaded):
    event = admin.get("/api/alerts", params={"q": "0412", "actionable": ""}).json()["items"][0]["id"]
    tickets = admin.get(f"/api/alerts/{event}/history").json()["tickets"]
    assert tickets
    number, boost = tickets[0]["number"], tickets[0]["parts"]["boost"]
    admin.post(f"/api/alerts/{event}/feedback", json={"verdict": "helpful", "ticket_number": number})
    again = {t["number"]: t for t in admin.get(f"/api/alerts/{event}/history").json()["tickets"]}
    assert again[number]["parts"]["boost"] == round(boost + 0.15, 2)  # the helpful mark lifts it at once, not after a cache expiry


def test_devices_page_is_stable_and_complete(admin, loaded):
    total = admin.get("/api/devices", params={"size": 2}).json()["total"]
    seen = []
    for page in range(1, total // 2 + 2):
        seen += [d["id"] for d in admin.get("/api/devices", params={"size": 2, "page": page}).json()["items"]]
    assert len(seen) == len(set(seen)) == total  # no device repeated or skipped across pages


def test_large_json_is_compressed(admin, loaded):
    r = admin.get("/api/insights/overview", params={"window": "all"}, headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_live_stream_is_never_compressed():
    from app.web import CompressExceptStream
    async def inner(scope, receive, send):
        # A compressible type, so only the path rule (not Starlette's own event-stream exclusion) keeps it plain.
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b"x" * 4096, "more_body": False})

    async def run(path):
        messages = []

        async def send(m):
            messages.append(m)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {"type": "http", "path": path, "method": "GET", "headers": [(b"accept-encoding", b"gzip")]}
        await CompressExceptStream(inner)(scope, receive, send)
        return dict(messages[0]["headers"])

    assert b"content-encoding" not in asyncio.run(run("/api/stream"))
    assert asyncio.run(run("/api/alerts")).get(b"content-encoding") == b"gzip"


def test_static_assets_have_cache_headers(client):
    font = client.get("/static/fonts/archivo-latin-wdth-normal.woff2")
    assert font.status_code == 200 and "max-age" in font.headers["cache-control"]
    shell = client.get("/alerts")  # every app route returns the single-page shell, which always revalidates
    assert shell.status_code == 200 and shell.headers["cache-control"] == "no-cache"
    assert '<meta name="csrf"' in shell.text
