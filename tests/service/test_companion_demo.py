from dataclasses import replace

from fastapi.testclient import TestClient

from companion_demo import create_app
from service.companion_service.config import CompanionSettings


def test_lightweight_companion_runtime_has_health_and_public_config(tmp_path):
    settings = CompanionSettings.from_env()
    settings = replace(
        settings,
        database_url=f"sqlite:///{tmp_path / 'companion.db'}",
        access_code="",
        profile_engine_api_key="",
        llm_api_key="",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/liveness").json() == {"status": "ok"}
        health = client.get("/api/health").json()
        assert health["status"] == "degraded"
        assert health["services"]["database"] == "ok"
        config = client.get("/api/v1/runtime/config").json()
        assert config["capabilities"]["profile_aware_text_chat"] is True
        assert config["capabilities"]["realtime_media"] is False
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
