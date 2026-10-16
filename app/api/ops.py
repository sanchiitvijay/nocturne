"""Live stream, ad-hoc diagnostics, simulation and custom alert triggers."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import db
from ..bus import bus
from ..cache import cache
from ..config import cfg
from ..security import client_ip, current_user, require
from ..services import classify, diagnostics
from ..services.simulator import SCENARIOS, simulator

router = APIRouter(prefix="/api", tags=["operations"])


@router.get("/stream")
async def stream(request: Request, user=Depends(current_user)):
    queue = bus.subscribe()

    async def events():
        try:
            yield f"event: hello\ndata: {{\"listeners\": {bus.listeners}}}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=cfg.live.heartbeat_seconds)
                    yield message
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class CheckRequest(BaseModel):
    host: str


@router.post("/diagnostics")
async def run_diagnostics(body: CheckRequest, request: Request, user=Depends(require("run_diagnostics"))):
    host = body.host.strip()
    if cfg.diagnostics.mode == "live" and cfg.diagnostics.get("adhoc_known_hosts_only", True) and diagnostics.valid_host(host) \
            and not await asyncio.to_thread(diagnostics.known_host, host):
        raise HTTPException(403, "Live checks only target devices in the inventory. Enter a device IP or name.")
    try:
        result = await diagnostics.run_checks(host)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    with db.session() as conn:
        db.audit(conn, user, "diagnostics.run", host, result["verdict"], client_ip(request))
    return result


# ── simulation ───────────────────────────────────────────────────────────────

@router.get("/sim/options")
def sim_options(user=Depends(require("simulate")), conn=Depends(db.get_conn)):
    def load_types():
        rows = db.rows(conn, """SELECT e.type_id, COALESCE(t.name, MAX(e.name)) name, COUNT(*) n FROM events e
                                LEFT JOIN event_types t ON t.type_id = e.type_id WHERE e.type_id IS NOT NULL
                                GROUP BY e.type_id ORDER BY n DESC LIMIT 80""")
        for t in rows:
            t["name"] = classify.event_name(t["type_id"], t["name"])
        return rows
    types = cache.get(conn, "sim_types", None, load_types)
    return {"scenarios": [{"id": k, **v} for k, v in SCENARIOS.items()], "status": simulator.status, "types": types,
            "limits": {"max_count": cfg.simulation.max_count, "count": cfg.simulation.default_count,
                       "interval_ms": cfg.simulation.default_interval_ms},
            "severities": dict(cfg.classification.severity_labels.items())}


class SimRun(BaseModel):
    scenario: str = "random"
    count: int = Field(default=12, ge=1)
    interval_ms: int = Field(default=900, ge=50, le=60000)
    site: str | None = None


@router.post("/sim/run")
async def sim_run(body: SimRun, request: Request, user=Depends(require("simulate"))):
    if body.scenario not in SCENARIOS:
        raise HTTPException(400, "Unknown scenario.")
    try:
        status = await simulator.run(body.scenario, body.count, body.interval_ms, body.site or None, user)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    with db.session() as conn:
        db.audit(conn, user, "simulation.start", body.scenario, f"{status['total']} alerts", client_ip(request))
    return status


@router.post("/sim/stop")
def sim_stop(request: Request, user=Depends(require("simulate"))):
    status = simulator.stop()
    with db.session() as conn:
        db.audit(conn, user, "simulation.stop", status.get("scenario") or "", ip=client_ip(request))
    return status


@router.get("/sim/status")
def sim_status(user=Depends(require("simulate"))):
    return simulator.status


class CustomAlert(BaseModel):
    device_id: int | None = None
    device_name: str | None = None
    ip: str | None = None
    site_code: str | None = None
    type_id: int | None = None
    name: str | None = None
    message: str = Field(min_length=3, max_length=2000)
    severity: str | None = None       # "auto" or P1..P4
    status_code: int | None = None
    repeat: int = Field(default=1, ge=1, le=50)
    interval_ms: int = Field(default=600, ge=0, le=60000)


@router.post("/sim/custom")
async def custom_alert(body: CustomAlert, request: Request, user=Depends(require("trigger_custom_alert"))):
    if not (body.device_id or (body.device_name or "").strip()):
        raise HTTPException(400, "Pick a device or type a new device name.")
    if not (body.type_id or (body.name or "").strip()):
        raise HTTPException(400, "Pick an event type or type a custom event name.")
    spec = body.model_dump()
    spec["scenario"] = "custom"
    created = []
    for i in range(body.repeat):
        created.append(await asyncio.to_thread(simulator.create_event, spec, "custom", user))
        if i < body.repeat - 1:
            await asyncio.sleep(body.interval_ms / 1000)
    with db.session() as conn:
        db.audit(conn, user, "alert.custom_trigger", created[0].get("device_name") or "", f"{body.repeat}× {created[0]['name']}", client_ip(request))
    return {"created": created}


class Preview(BaseModel):
    type_id: int | None = None
    name: str | None = None
    message: str = ""


@router.post("/sim/preview")
def preview(body: Preview, user=Depends(require("trigger_custom_alert"))):
    """Show how the classification rules will treat a custom alert before it is sent."""
    name = (body.name or "").strip() or classify.event_name(body.type_id, None)
    result = classify.classify(body.type_id, name, body.message)
    result["name"] = name
    result["severity_label"] = classify.severity_label(result["severity"])
    return result
