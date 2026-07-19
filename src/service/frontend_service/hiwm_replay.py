"""Read/delete API for verified HIWM ledgers without exposing raw media."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from engine_utils.directory_info import DirectoryInfo
from handlers.hiwm.ledger import ImmutableJSONLLedger
from handlers.hiwm.models import LockedPredictionRecord, LockedSafetyFallbackRecord
from .runtime_control import require_runtime_control_access, runtime_control_auth_required


_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")
_MAX_EVENTS = 200
_MAX_LINE_BYTES = 2_000_000


def _hiwm_config(handler_manager: Any) -> Any:
    registries = getattr(handler_manager, "handler_registries", None)
    if not isinstance(registries, dict):
        return None
    registry = registries.get("HIWM")
    return getattr(registry, "handler_config", None) if registry is not None else None


def resolve_ledger_root(handler_manager: Any) -> Optional[Path]:
    config = _hiwm_config(handler_manager)
    value = getattr(config, "ledger_dir", None) if config is not None else None
    if not isinstance(value, str) or not value:
        return None
    root = Path(value)
    if not root.is_absolute():
        root = Path(DirectoryInfo.get_project_dir()) / root
    return root.resolve()


def resolve_session_ledger(root: Path, session_id: str) -> Path:
    if not _SAFE_SESSION_ID.fullmatch(session_id):
        raise ValueError("invalid session id")
    candidate = (root / f"{session_id}.jsonl").resolve()
    if candidate.parent != root.resolve():
        raise ValueError("invalid session ledger path")
    return candidate


def load_verified_timeline(root: Path, session_id: str) -> list[dict[str, Any]]:
    path = resolve_session_ledger(root, session_id)
    if not path.exists():
        return []
    lines = path.read_bytes().splitlines()[-_MAX_EVENTS:]
    events: list[dict[str, Any]] = []
    for raw_line in lines:
        if not raw_line.strip():
            continue
        if len(raw_line) > _MAX_LINE_BYTES:
            raise ValueError("ledger event exceeds replay size limit")
        try:
            record = LockedPredictionRecord.model_validate_json(raw_line)
            if not ImmutableJSONLLedger.verify(record):
                raise ValueError("prediction lock verification failed")
            event_type = "prediction"
        except ValidationError:
            record = LockedSafetyFallbackRecord.model_validate_json(raw_line)
            if not ImmutableJSONLLedger.verify_fallback(record):
                raise ValueError("fallback lock verification failed")
            event_type = "safe_fallback"
        events.append(
            {
                "event_type": event_type,
                "record": record.model_dump(mode="json"),
            }
        )
    return events


def register_hiwm_replay(app: FastAPI, handler_manager: Any) -> None:
    """Register bounded, local-session replay and deletion endpoints."""

    @app.get("/openavatarchat/hiwm/sessions/{session_id}/timeline")
    async def get_hiwm_timeline(session_id: str, request: Request):
        if runtime_control_auth_required():
            require_runtime_control_access(request)
        root = resolve_ledger_root(handler_manager)
        if root is None:
            raise HTTPException(status_code=404, detail="HIWM is not enabled")
        try:
            events = load_verified_timeline(root, session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return JSONResponse(
            content={
                "schema_version": "1.0",
                "session_id": session_id,
                "raw_media_persisted": False,
                "events": events,
            }
        )

    @app.delete("/openavatarchat/hiwm/sessions/{session_id}")
    async def delete_hiwm_session(session_id: str, request: Request):
        if runtime_control_auth_required():
            require_runtime_control_access(request)
        root = resolve_ledger_root(handler_manager)
        if root is None:
            raise HTTPException(status_code=404, detail="HIWM is not enabled")
        try:
            path = resolve_session_ledger(root, session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        removed = path.exists()
        if removed:
            path.unlink()
        return JSONResponse(
            content={"session_id": session_id, "deleted": removed}
        )
