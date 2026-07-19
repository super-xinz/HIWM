"""Append-only durable prediction ledger used before any utterance is emitted."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .models import (
    LockProof,
    LockedPredictionRecord,
    LockedSafetyFallbackRecord,
    PredictionPayload,
    SafetyFallbackPayload,
)


def canonical_json_bytes(value: Union[PredictionPayload, Dict[str, Any]]) -> bytes:
    if isinstance(value, PredictionPayload):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def prediction_sha256(value: Union[PredictionPayload, Dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class ImmutableJSONLLedger:
    """Write one canonical JSON object per line with flush + fsync semantics."""

    _safe_id = re.compile(r"[^A-Za-z0-9_.-]+")

    def __init__(self, root_dir: Union[str, Path], session_id: str):
        safe_session_id = self._safe_id.sub("_", session_id).strip("._")
        if not safe_session_id:
            raise ValueError("session_id cannot be converted to a safe ledger name")
        self.root_dir = Path(root_dir)
        self.path = self.root_dir / f"{safe_session_id}.jsonl"
        self._lock = threading.Lock()

    def append(self, payload: PredictionPayload) -> LockedPredictionRecord:
        payload_dict = payload.model_dump(mode="json")
        digest = prediction_sha256(payload_dict)
        locked = LockedPredictionRecord.model_validate(
            {
                **payload_dict,
                "locked_prediction": LockProof(
                    prediction_id=payload.turn_id,
                    action_id=payload.selected_action_id,
                    sha256=digest,
                    locked_at=payload.locked_at,
                ).model_dump(mode="json"),
            }
        )
        line = canonical_json_bytes(locked.model_dump(mode="json")) + b"\n"

        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "ab") as ledger_file:
                ledger_file.write(line)
                ledger_file.flush()
                os.fsync(ledger_file.fileno())
        return locked

    def append_fallback(
        self, payload: SafetyFallbackPayload
    ) -> LockedSafetyFallbackRecord:
        """Durably lock an explicit probability-free clarification/wait exit."""

        payload_dict = payload.model_dump(mode="json")
        digest = prediction_sha256(payload_dict)
        locked = LockedSafetyFallbackRecord.model_validate(
            {
                **payload_dict,
                "locked_prediction": LockProof(
                    prediction_id=payload.turn_id,
                    action_id=payload.action_id,
                    sha256=digest,
                    locked_at=payload.locked_at,
                ).model_dump(mode="json"),
            }
        )
        line = canonical_json_bytes(locked.model_dump(mode="json")) + b"\n"
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "ab") as ledger_file:
                ledger_file.write(line)
                ledger_file.flush()
                os.fsync(ledger_file.fileno())
        return locked

    @staticmethod
    def verify_fallback(record: LockedSafetyFallbackRecord) -> bool:
        payload = record.model_dump(mode="json")
        proof = payload.pop("locked_prediction")
        return (
            proof.get("algorithm") == "sha256"
            and proof.get("prediction_id") == record.turn_id
            and proof.get("action_id") == record.action_id
            and proof.get("locked_at") == record.locked_at
            and prediction_sha256(payload) == proof.get("sha256")
        )

    @staticmethod
    def verify(record: LockedPredictionRecord) -> bool:
        # Preserve the exact field set of legacy v1 records. New optional
        # planner fields receive safe defaults at validation time, but adding
        # those defaults before hashing would otherwise invalidate an old,
        # correctly locked line.
        payload = record.model_dump(mode="json", exclude_unset=True)
        proof = payload.pop("locked_prediction")
        return (
            proof.get("algorithm") == "sha256"
            and proof.get("prediction_id") == record.turn_id
            and proof.get("action_id") == record.selected_action_id
            and proof.get("locked_at") == record.locked_at
            and prediction_sha256(payload) == proof.get("sha256")
        )

    def read_last(self) -> Optional[LockedPredictionRecord]:
        if not self.path.exists():
            return None
        last_nonempty: Optional[bytes] = None
        with self.path.open("rb") as ledger_file:
            for line in ledger_file:
                if line.strip():
                    last_nonempty = line
        if last_nonempty is None:
            return None
        record = LockedPredictionRecord.model_validate_json(last_nonempty)
        if not self.verify(record):
            raise ValueError(f"ledger integrity check failed: {self.path}")
        return record
