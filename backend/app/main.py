"""FastAPI entry point. Placeholder until integration: health check + static SPA only.
Lead-owned; routes are wired in the integration phase."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Verity")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="spa")
