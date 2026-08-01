"""Lightweight production entrypoint for the profile-aware text demo.

The full HIWM runtime remains available through ``src/demo.py``.  This entry
does not load RTC/VAD/avatar model assets, so the web + BFF demo has a small,
deterministic Zeabur startup surface.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from project_identity import API_VERSION, PROJECT_NAME, PROJECT_SLUG, PROJECT_VERSION
from service.companion_service import register_companion_api
from service.companion_service.config import CompanionSettings


# Local operators can copy .env.example to .env. Zeabur still injects the
# same values as service variables and takes precedence over this file.
load_dotenv()


def create_app(settings: CompanionSettings | None = None) -> FastAPI:
    app = FastAPI(
        title=f"{PROJECT_NAME} Companion Demo",
        version=PROJECT_VERSION,
        description="Profile-aware chat BFF and HIWM web client.",
    )
    register_companion_api(app, settings=settings)

    @app.get("/version")
    async def version() -> dict:
        return {
            "name": PROJECT_NAME,
            "slug": PROJECT_SLUG,
            "version": PROJECT_VERSION,
            "api_version": API_VERSION,
            "runtime": "companion",
        }

    @app.get("/liveness")
    async def liveness() -> dict:
        return {"status": "ok"}

    @app.get("/readiness")
    async def readiness() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/runtime/config")
    async def runtime_config() -> dict:
        return {
            "api_config": {
                "schema_version": "1.1",
                "asr": None,
                "hiwm": None,
                "tts": None,
            },
            "ui_config": {"mode": "companion", "debug": False},
            "capabilities": {
                "profile_aware_text_chat": True,
                "realtime_media": False,
                "raw_media_persisted": False,
            },
        }

    frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if frontend.exists():
        app.mount("/ui", StaticFiles(directory=frontend, html=True), name="ui")

        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse("/ui/index.html")
    else:
        @app.get("/", include_in_schema=False)
        async def missing_frontend() -> dict:
            return {
                "status": "degraded",
                "message": "frontend/dist is missing; run pnpm build before starting",
            }
    return app


app = create_app()


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
