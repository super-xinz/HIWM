from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from service.frontend_service.runtime_control import (
    RUNTIME_CONTROL_TOKEN_ENV,
    require_runtime_control_access,
)


def _request(host: str, authorization: str | None = None) -> Request:
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("utf-8")))
    return Request({"type": "http", "client": (host, 443), "headers": headers})


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_runtime_control_allows_loopback_without_shared_token(monkeypatch, host):
    monkeypatch.delenv(RUNTIME_CONTROL_TOKEN_ENV, raising=False)

    require_runtime_control_access(_request(host))


def test_runtime_control_rejects_unauthenticated_remote_client(monkeypatch):
    monkeypatch.delenv(RUNTIME_CONTROL_TOKEN_ENV, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_runtime_control_access(_request("192.0.2.10"))

    assert exc_info.value.status_code == 403


def test_runtime_control_accepts_matching_remote_bearer_token(monkeypatch):
    token = "runtime-control-unit-test-token"
    monkeypatch.setenv(RUNTIME_CONTROL_TOKEN_ENV, token)

    require_runtime_control_access(
        _request("192.0.2.10", authorization=f"Bearer {token}")
    )

    with pytest.raises(HTTPException):
        require_runtime_control_access(
            _request("192.0.2.10", authorization="Bearer wrong-token")
        )
