"""Access guard for local runtime-control endpoints.

Loopback clients are allowed by default. Non-loopback deployments must set a
shared bearer token so an unauthenticated network client cannot replace the
process credential or terminate another RTC signaling session.
"""

from __future__ import annotations

import ipaddress
import os
import secrets

from fastapi import HTTPException, Request


RUNTIME_CONTROL_TOKEN_ENV = "HIWM_RUNTIME_CONTROL_TOKEN"


def runtime_control_auth_required() -> bool:
    """Report whether remote control requests require a bearer token."""

    return bool(os.environ.get(RUNTIME_CONTROL_TOKEN_ENV, "").strip())


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def require_runtime_control_access(request: Request) -> None:
    """Allow local-only access, or require the configured bearer token."""

    client_host = request.client.host if request.client is not None else None
    expected_token = os.environ.get(RUNTIME_CONTROL_TOKEN_ENV, "").strip()
    authorization = request.headers.get("authorization", "")
    scheme, separator, provided_token = authorization.partition(" ")
    if (
        expected_token
        and separator
        and scheme.lower() == "bearer"
        and secrets.compare_digest(provided_token, expected_token)
    ):
        return

    # With no shared token, keep the workstation behavior local-only. When a
    # token is configured (the cloud case), require it even if a reverse proxy
    # presents as loopback so the proxy cannot accidentally bypass the guard.
    if not expected_token and _is_loopback(client_host):
        return

    raise HTTPException(
        status_code=403,
        detail=(
            "远程运行控制已禁用；请从本机访问，或配置 "
            f"{RUNTIME_CONTROL_TOKEN_ENV} 并提供 Bearer Token"
        ),
    )
