"""Application factory: middleware, API routers and the single-page React app (built into web/dist)."""
from __future__ import annotations

import asyncio
import html
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from . import db, navigation, security
from .api import admin, alerts, auth, data, inventory, ops
from .bus import bus
from .config import ROOT, cfg, secret_key
from .services.etl.runner import runner

WEB = ROOT / "web"
DIST = WEB / "dist"  # output of `npm run build` in frontend/


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    default_password = security.ensure_admin()
    if default_password:
        print(f"\n  NOCTURNE: created administrator '{cfg.security.admin_username}' with password '{default_password}'."
              "\n  You will be asked to change it at first sign-in.\n")
    bus.bind(asyncio.get_running_loop())
    runner.start()
    yield


# The API explorer and schema are served by guarded routes below, so they need a session like every other endpoint.
app = FastAPI(title=f"{cfg.app.name} API", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=secret_key(), session_cookie="nocturne_session",
                   max_age=cfg.security.session_hours * 3600, same_site="lax", https_only=bool(cfg.security.cookie_secure))

# Pages use inline scripts and style attributes, so those stay allowed; everything else is limited to this origin.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
# Swagger UI loads its assets from jsDelivr.
CSP_DOCS = CSP.replace("script-src 'self'", "script-src 'self' https://cdn.jsdelivr.net").replace(
    "style-src 'self'", "style-src 'self' https://cdn.jsdelivr.net").replace("img-src 'self' data:", "img-src 'self' data: https://fastapi.tiangolo.com")


class CompressExceptStream:
    """Gzip responses (dashboard and list JSON shrink 5-10x) but never the live stream, which must flush each event."""

    def __init__(self, app):
        self.plain, self.gzip = app, GZipMiddleware(app, minimum_size=1024)

    async def __call__(self, scope, receive, send):
        target = self.plain if scope["type"] != "http" or scope["path"] == "/api/stream" else self.gzip
        await target(scope, receive, send)


app.add_middleware(CompressExceptStream)

# Built bundles under /assets carry a content hash in their names, so they can be cached for a year. Fonts and images
# under /static rarely change; the app shell itself always revalidates so a new build shows at once.
STATIC_CACHE = {".woff2": "public, max-age=604800", ".png": "public, max-age=86400", ".svg": "public, max-age=86400",
                ".css": "no-cache", ".js": "no-cache"}
IMMUTABLE = "public, max-age=31536000, immutable"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", CSP_DOCS if request.url.path == "/api/docs" else CSP)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/assets/") and response.status_code == 200:
        response.headers.setdefault("Cache-Control", IMMUTABLE)
    elif path.startswith("/static/") or path == "/favicon.ico":
        rule = STATIC_CACHE.get(Path(path).suffix.lower()) or ("public, max-age=86400" if path == "/favicon.ico" else None)
        if rule:
            response.headers.setdefault("Cache-Control", rule)
    return response


for r in (auth.router, alerts.router, inventory.router, ops.router, data.router, admin.router):
    app.include_router(r)
app.mount("/static", StaticFiles(directory=str(WEB / "static")), name="static")
app.mount("/assets", StaticFiles(directory=str(DIST / "assets"), check_dir=False), name="assets")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    if exc.status_code == 401:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    return _shell(request, status=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "request"
    return JSONResponse({"error": f"{field}: {first.get('msg', 'invalid value')}"}, status_code=422)


@app.get("/api/openapi.json", include_in_schema=False)
def openapi_schema(user=Depends(security.current_user)):
    return JSONResponse(app.openapi())


@app.get("/api/docs", include_in_schema=False)
def api_docs(request: Request):
    if not security.session_user(request):
        raise HTTPException(401, "Sign in to continue.")
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title=f"{cfg.app.name} API")


@app.get("/api/meta", tags=["system"])
def meta():
    """Product name and organisation for the sign-in screen (public, nothing sensitive)."""
    return navigation.public_meta()


@app.get("/api/health", tags=["system"])
def health():
    with db.session() as conn:
        return {"status": "ok", "events": db.scalar(conn, "SELECT COUNT(*) FROM events", default=0),
                "data_version": db.data_version(conn)}


# ── single-page app ──────────────────────────────────────────────────────────
# Every non-API path returns the app shell; the React router decides what to show and which role may see it.
# The shell carries the session's CSRF token in <meta name="csrf">, which the app sends back on every write.

_CSRF_META = re.compile(r'<meta name="csrf" content="[^"]*"\s*/?>')
_NOT_BUILT = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="csrf" content="">
<title>{name}</title></head><body style="font-family:system-ui;padding:40px">
<h1>{name}</h1><p>The web interface has not been built yet. Run <code>npm install &amp;&amp; npm run build</code> in
<code>frontend/</code>, or <code>npm run dev</code> there while developing.</p></body></html>"""


class _Shell:
    """index.html from the last build, re-read when the file changes."""

    def __init__(self) -> None:
        self._html, self._mtime = "", -1.0

    def text(self) -> str:
        index = DIST / "index.html"
        try:
            mtime = index.stat().st_mtime
        except FileNotFoundError:
            return _NOT_BUILT.format(name=html.escape(cfg.app.name))
        if mtime != self._mtime:
            self._html, self._mtime = index.read_text(encoding="utf-8"), mtime
        return self._html


shell = _Shell()


def _shell(request: Request, status: int = 200) -> HTMLResponse:
    token = html.escape(request.session.get("csrf", ""), quote=True)
    body = _CSRF_META.sub(lambda _: f'<meta name="csrf" content="{token}">', shell.text(), count=1)
    return HTMLResponse(body, status_code=status, headers={"Cache-Control": "no-cache"})


@app.get("/guide", include_in_schema=False)
def guide(request: Request):
    if not security.session_user(request):
        raise HTTPException(401, "Sign in to continue.")
    return FileResponse(ROOT / "docs" / "NOCTURNE-Guide.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(WEB / "static" / "img" / "ferguson-mark.png")


@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
def spa(full_path: str, request: Request):
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(404, "Not found.")
    # Signed-out visitors go straight to the sign-in screen (and signed-in ones skip it), before any script loads.
    signed_in = security.session_user(request) is not None
    if full_path == "login":
        return RedirectResponse("/", status_code=303) if signed_in else _shell(request)
    if not signed_in:
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?next={quote(target, safe='/')}" if target != "/" else "/login", status_code=303)
    return _shell(request)
