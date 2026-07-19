"""Read-only robot adapter over verified, pre-execution HIWM decisions.

The adapter deliberately exposes no arbitrary motion endpoint. A robot polls
speech decisions, deduplicates by ``turn_id``, and keeps responsibility for its
own device safety, actuation policy, and emergency stop.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from project_identity import API_PREFIX
from .hiwm_replay import load_verified_timeline, resolve_ledger_root
from .runtime_control import require_runtime_control_access, runtime_control_auth_required


def _command_from_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event["event_type"]
    record = event["record"]
    proof = record["locked_prediction"]

    if event_type == "prediction":
        selected_action_id = record["selected_action_id"]
        selected = next(
            (
                action
                for action in record["actions"]
                if action["action_id"] == selected_action_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("verified prediction has no selected action")
        strategy = selected["strategy"]
        utterance = selected["utterance"]
        fallback = False
    elif event_type == "safe_fallback":
        selected_action_id = record["action_id"]
        strategy = selected_action_id
        utterance = record["utterance"]
        fallback = True
    else:
        raise ValueError(f"unsupported ledger event type: {event_type}")

    return {
        "schema_version": "1.0",
        "cursor": record["turn_id"],
        "idempotency_key": f'{record["session_id"]}:{record["turn_id"]}',
        "session_id": record["session_id"],
        "turn_id": record["turn_id"],
        "issued_at": record["locked_at"],
        "command": {
            "type": "speak",
            "strategy": strategy,
            "text": utterance,
            "fallback": fallback,
        },
        "source_lock": {
            "algorithm": proof["algorithm"],
            "sha256": proof["sha256"],
            "prediction_id": proof["prediction_id"],
            "action_id": selected_action_id,
        },
    }


def build_robot_command_feed(
    events: list[dict[str, Any]],
    *,
    after_turn_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Convert verified ledger events into ordered, idempotent robot commands."""

    commands = [_command_from_event(event) for event in events]
    if after_turn_id is None:
        return commands
    cursor_index = next(
        (
            index
            for index, command in enumerate(commands)
            if command["turn_id"] == after_turn_id
        ),
        None,
    )
    if cursor_index is None:
        raise ValueError("after_turn_id is not present in the bounded ledger window")
    return commands[cursor_index + 1 :]


def register_robot_action_api(app: FastAPI, handler_manager: Any) -> None:
    """Register the stable v1 polling contract for robot speech adapters."""

    def authorize(request: Request) -> None:
        if runtime_control_auth_required():
            require_runtime_control_access(request)

    @app.get(f"{API_PREFIX}/robot/capabilities")
    async def get_robot_capabilities(request: Request):
        authorize(request)
        return JSONResponse(
            content={
                "schema_version": "1.0",
                "delivery": "verified_ledger_poll",
                "supported_commands": ["speak"],
                "physical_motion_enabled": False,
                "raw_media_exposed": False,
                "ordering": "ledger_order",
                "idempotency": "session_id:turn_id",
                "exactly_once_delivery": False,
            }
        )

    @app.get(f"{API_PREFIX}/robot/sessions/{{session_id}}/commands")
    async def get_robot_commands(
        session_id: str,
        request: Request,
        after_turn_id: Optional[str] = None,
    ):
        authorize(request)
        root = resolve_ledger_root(handler_manager)
        if root is None:
            raise HTTPException(status_code=404, detail="HIWM is not enabled")
        try:
            events = load_verified_timeline(root, session_id)
            commands = build_robot_command_feed(
                events,
                after_turn_id=after_turn_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return JSONResponse(
            content={
                "schema_version": "1.0",
                "session_id": session_id,
                "delivery": "at_least_once",
                "next_cursor": commands[-1]["cursor"] if commands else after_turn_id,
                "commands": commands,
            }
        )
