import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from backend.database import init_db
from backend.auth import get_current_user, SESSION_SECRET
from backend.routers import extensions, trunk, settings, routes, voicemail, time_conditions, ring_groups, update
from backend.routers import auth as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize engine (picks up BPX_DATA_DIR env var) and create all SQLModel tables
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

# Session middleware — must be added before routers (SEC-04)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="bpx_session",
    max_age=24 * 60 * 60,   # 24-hour sliding session (D-11)
    same_site="lax",
    https_only=False,        # HA ingress uses HTTP internally — MUST be False (RESEARCH.md Pitfall 2)
)

# Dist dir is test-resolvable via BPX_DIST_DIR (default = in-container path). Both the
# static asset mount and the SPA index resolve from the SAME base so they stay consistent
# (and so the ingress regression test can point at a fixture index.html).
_DIST_DIR = Path(os.environ.get("BPX_DIST_DIR", "/app/frontend/dist"))

# Static assets FIRST — must be before catch-all route (prevents Pitfall 2)
_frontend_assets = _DIST_DIR / "assets"
try:
    app.mount("/assets", StaticFiles(directory=str(_frontend_assets)), name="assets")
except Exception:
    # Frontend not built yet — skip static mount; serve only API + SPA shell
    pass

# Auth router (PUBLIC — no get_current_user dependency)
app.include_router(auth_router.router, prefix="/api")

# API routers — all protected by get_current_user
app.include_router(extensions.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(trunk.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(settings.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(routes.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(voicemail.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(time_conditions.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(ring_groups.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(update.router, prefix="/api", dependencies=[Depends(get_current_user)])

# SPA shell — serve the BUILT dist/index.html so hashed asset + CSS names always
# match the actual Vite output. A hand-maintained template drifts every build and
# silently breaks the app (white screen: HTML served in place of a missing index.js).
_dist_index = _DIST_DIR / "index.html"
_INGRESS_FALLBACK = 'window.__INGRESS_PATH__ = window.__INGRESS_PATH__ || "";'
# Stable marker anchor emitted by frontend/index.html — replace target the build never
# minifies away. If absent (older build) we fall back to the exact fallback-line replace.
_INGRESS_MARKER = "<!--INGRESS_PATH-->"
# HA-supplied ingress prefix: must be exactly /api/hassio_ingress/<token>. Validate the
# shape and reject anything with HTML/quote metacharacters before embedding (T-06-01).
_INGRESS_PATH_RE = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9_-]+$")


def _safe_ingress_path(raw: str) -> str:
    """Return the ingress path only if it matches the expected shape, else ''."""
    if raw and _INGRESS_PATH_RE.match(raw):
        return raw
    return ""


@app.get("/{full_path:path}")
async def spa_catch_all(request: Request, full_path: str):
    ingress_path = _safe_ingress_path(request.headers.get("X-Ingress-Path", ""))
    try:
        html = _dist_index.read_text()
    except FileNotFoundError:
        return HTMLResponse("<h1>ha-phone</h1><p>Frontend not built.</p>", status_code=200)

    # 1. Inject the real (validated) ingress path so window.__INGRESS_PATH__ is populated.
    #    Prefer the stable marker comment; fall back to the exact fallback line; both keep
    #    the served HTML ending with a populated assignment.
    inject_script = f'<script>window.__INGRESS_PATH__ = "{ingress_path}";</script>'
    if _INGRESS_MARKER in html:
        html = html.replace(_INGRESS_MARKER, inject_script)
    elif _INGRESS_FALLBACK in html:
        html = html.replace(_INGRESS_FALLBACK, f'window.__INGRESS_PATH__ = "{ingress_path}";')
    else:
        # Last-resort: inject right after <head> so the value is never left unset.
        html = re.sub(r"(<head[^>]*>)", r"\1" + inject_script, html, count=1)

    # 2. Asset resolution fix (the confirmed live failure mode): Vite emits relative
    #    ./assets/* refs (base "./"). Under the ingress URL these resolve against the
    #    current document path, so on a deep route (/<token>/extensions) ./assets/* 404s
    #    → blank iframe. Rewrite ./assets/ to the ingress-prefixed absolute path so the
    #    StaticFiles mount at /assets is always reached (HA strips the prefix → backend
    #    still sees /assets/...). With no prefix the refs stay relative (root-served).
    if ingress_path:
        html = html.replace('"./assets/', f'"{ingress_path}/assets/')
        html = html.replace("'./assets/", f"'{ingress_path}/assets/")

    return HTMLResponse(html)
