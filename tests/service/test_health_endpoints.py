from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chat_engine.chat_engine as chat_engine_module
from chat_engine.chat_engine import ChatEngine


def _initialized_app(monkeypatch, tmp_path):
    dotenv_calls = []
    monkeypatch.setattr(
        chat_engine_module,
        "load_dotenv",
        lambda: dotenv_calls.append("blocked"),
    )

    engine = ChatEngine()
    monkeypatch.setattr(engine.handler_manager, "initialize", lambda *_args: None)
    monkeypatch.setattr(
        engine.handler_manager,
        "load_handlers",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(engine.logic_manager, "initialize", lambda *_args: None)
    monkeypatch.setattr(engine.logic_manager, "load_logics", lambda *_args: None)

    app = FastAPI()
    engine.initialize(
        SimpleNamespace(model_root=str(tmp_path)),
        app=app,
    )
    assert dotenv_calls == ["blocked"]
    return engine, app


def test_liveness_is_ok_and_readiness_tracks_engine_state(monkeypatch, tmp_path):
    engine, app = _initialized_app(monkeypatch, tmp_path)

    with TestClient(app) as client:
        assert client.get("/liveness").status_code == 200
        assert client.get("/liveness").json() == {"status": "ok"}
        assert client.get("/readiness").status_code == 200
        assert client.get("/readiness").json() == {"status": "ok"}

        engine.states.inited = False
        response = client.get("/readiness")
        assert response.status_code == 500
        assert response.json() == {
            "detail": "Chat engine is not ready yet."
        }
