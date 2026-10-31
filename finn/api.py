"""HTTP API + the app itself, on one port.

Research for a new symbol takes 20–60s the first time (PDFs), so it runs as a
background job the app polls; the app shows the stage it's on. Cached
dossiers return immediately.
"""
from __future__ import annotations

import json
import os
import threading
import time

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import llm
from .config import DATA_OUT, WEB_DIR

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
SNAPSHOT_TTL = 30 * 60


def _snapshot_path():
    real = DATA_OUT / "snapshot.json"
    return real if real.exists() else DATA_OUT / "sample" / "snapshot.json"


def _refresh_in_background():
    from .push import digest

    try:
        snap = digest.build(log=lambda *_: None)
        priced = sum(1 for h in snap["holdings"] if h["eod"])
        # A blocked or half-failed fetch must never replace good data with an empty feed.
        if snap["filings"] and priced >= len(snap["holdings"]) // 2:
            digest.write(snap)
    except Exception:
        pass
    finally:
        with _lock:
            _jobs.pop("__refresh__", None)


async def snapshot(request):
    path = _snapshot_path()
    stale = not path.exists() or time.time() - path.stat().st_mtime > SNAPSHOT_TTL
    auto = os.getenv("FINN_AUTO_REFRESH") == "1"   # off by default: a free server has little memory
    if request.query_params.get("refresh") or (auto and stale and "sample" not in str(path)):
        with _lock:
            if "__refresh__" not in _jobs:
                _jobs["__refresh__"] = {}
                threading.Thread(target=_refresh_in_background, daemon=True).start()
    if not path.exists():
        return JSONResponse({"error": "No snapshot yet. Run: python -m finn refresh"}, status_code=503)
    return FileResponse(path, media_type="application/json")


def _run(symbol: str):
    from .pull import research

    def progress(stage):
        _jobs[symbol]["stage"] = stage

    try:
        d = research.build(symbol, progress)
        research.write(d)
        _jobs[symbol].update(state="done")
    except LookupError as e:
        _jobs[symbol].update(state="error", error=str(e))
    except Exception as e:  # network trouble, a broken PDF, …
        _jobs[symbol].update(state="error", error=f"Research failed: {e}"[:200])


async def research(request):
    symbol = request.path_params["symbol"].upper()
    path = DATA_OUT / "research" / f"{symbol}.json"
    sample = DATA_OUT / "sample" / "research" / f"{symbol}.json"
    if not path.exists() and sample.exists():
        return FileResponse(sample, media_type="application/json")
    fresh = request.query_params.get("fresh")
    if path.exists() and not fresh:
        return FileResponse(path, media_type="application/json")
    with _lock:
        job = _jobs.get(symbol)
        if job and job["state"] == "done" and path.exists():
            _jobs.pop(symbol)
            return FileResponse(path, media_type="application/json")
        if not job or job["state"] == "error" and request.method == "POST":
            job = _jobs[symbol] = {"state": "running", "stage": "Starting", "started": time.time()}
            threading.Thread(target=_run, args=(symbol,), daemon=True).start()
    return JSONResponse({"job": job}, status_code=202 if job["state"] == "running" else 404)


async def health(request):
    return JSONResponse({"ok": True, "model": llm.describe()})


async def index(request):
    return FileResponse(WEB_DIR / "index.html")


app = Starlette(
    routes=[
        Route("/api/health", health),
        Route("/api/snapshot", snapshot),
        Route("/api/research/{symbol}", research, methods=["GET", "POST"]),
        Route("/", index),
        Mount("/", StaticFiles(directory=WEB_DIR), name="web"),
    ],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])],
)
