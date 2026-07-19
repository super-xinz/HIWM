"""Strictly public API runtime metadata for the Web UI.

Only explicitly whitelisted, non-secret fields are returned.  This module must
never serialize a handler config wholesale.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional


_DASHSCOPE_KEY_ENV = "DASHSCOPE_API_KEY"
_UNCONFIGURED_SENTINELS = frozenset({"NOT_CONFIGURED_YET"})
_RUNTIME_KEY_HANDLER_NAMES = (
    "BailianASR",
    "HIWM",
    "BailianTTS",
    # Older profiles register the same Bailian TTS handler under this name.
    "CosyVoice",
)


def _get_handler_config(handler_manager: Any, *names: str) -> Any:
    if handler_manager is None:
        return None
    registries = getattr(handler_manager, "handler_registries", None)
    if not isinstance(registries, dict):
        return None
    for name in names:
        registry = registries.get(name)
        if registry is not None:
            return getattr(registry, "handler_config", None)
    return None


def _text(config: Any, field: str) -> Optional[str]:
    value = getattr(config, field, None) if config is not None else None
    return value if isinstance(value, str) and value else None


def _integer(config: Any, field: str) -> Optional[int]:
    value = getattr(config, field, None) if config is not None else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(config: Any, field: str) -> Optional[float]:
    value = getattr(config, field, None) if config is not None else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _boolean(config: Any, field: str) -> Optional[bool]:
    value = getattr(config, field, None) if config is not None else None
    return value if isinstance(value, bool) else None


def _string_list(config: Any, field: str) -> Optional[list[str]]:
    value = getattr(config, field, None) if config is not None else None
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) and item for item in value
    ):
        return None
    return list(value)


def _is_configured(config: Any, key_env: str) -> bool:
    """Report credential presence without reading or serializing its value."""
    if config is None:
        return False
    configured_value = getattr(config, "api_key", None)
    candidates = (configured_value, os.environ.get(key_env))
    return any(
        isinstance(value, str)
        and bool(value.strip())
        and value.strip() not in _UNCONFIGURED_SENTINELS
        for value in candidates
    )


def build_public_api_config(handler_manager: Any) -> dict[str, Any]:
    """Build the fixed, secret-free ``initconfig.api_config`` contract."""
    asr = _get_handler_config(handler_manager, "BailianASR")
    hiwm = _get_handler_config(handler_manager, "HIWM")
    tts = _get_handler_config(handler_manager, "BailianTTS", "CosyVoice")

    hiwm_key_env = _text(hiwm, "api_key_env") or _DASHSCOPE_KEY_ENV
    hiwm_model = _text(hiwm, "model_name")

    return {
        "schema_version": "1.1",
        "asr": {
            "provider": "dashscope" if asr is not None else None,
            "model": _text(asr, "model_name"),
            "endpoint": _text(asr, "base_websocket_url"),
            "key_env": _DASHSCOPE_KEY_ENV,
            "configured": _is_configured(asr, _DASHSCOPE_KEY_ENV),
            "sample_rate": _integer(asr, "sample_rate"),
            "format": _text(asr, "format"),
        },
        "hiwm": {
            "provider": "dashscope" if hiwm is not None else None,
            "model": hiwm_model,
            "endpoint": _text(hiwm, "api_url"),
            "key_env": hiwm_key_env,
            "configured": _is_configured(hiwm, hiwm_key_env),
            "timeout_seconds": _number(hiwm, "request_timeout_seconds"),
            "temperature": _number(hiwm, "temperature"),
            "streaming": False if hiwm is not None else None,
            "response_format": (
                "json_object"
                if _boolean(hiwm, "structured_output") is True
                else None
            ),
            "input_modalities": _string_list(hiwm, "input_modalities"),
            "structured_output": _boolean(hiwm, "structured_output"),
            "thinking_enabled": _boolean(hiwm, "enable_thinking"),
        },
        "tts": {
            "provider": "dashscope" if tts is not None else None,
            "model": _text(tts, "model_name"),
            # Bailian TTS currently delegates transport selection to the SDK;
            # there is no endpoint in its explicit runtime config.  Do not guess.
            "endpoint": _text(tts, "endpoint"),
            "key_env": _DASHSCOPE_KEY_ENV,
            "configured": _is_configured(tts, _DASHSCOPE_KEY_ENV),
            "voice": _text(tts, "voice"),
            "sample_rate": _integer(tts, "sample_rate"),
        },
    }


def configure_runtime_api_key(handler_manager: Any, api_key: str) -> dict[str, Any]:
    """Install one DashScope key in process memory without persisting it.

    The returned value is the same fixed, secret-free contract used by the
    initialization endpoint. The credential itself is deliberately never
    returned, logged, or written to ``.env``.
    """

    normalized_key = api_key.strip() if isinstance(api_key, str) else ""
    if len(normalized_key) < 8 or len(normalized_key) > 512:
        raise ValueError("API Key 长度无效，请检查后重试")
    if normalized_key in _UNCONFIGURED_SENTINELS:
        raise ValueError("该值不是有效的 API Key")

    registries = getattr(handler_manager, "handler_registries", None)
    if not isinstance(registries, dict):
        raise RuntimeError("运行时处理器尚未就绪")

    os.environ[_DASHSCOPE_KEY_ENV] = normalized_key

    for handler_name in _RUNTIME_KEY_HANDLER_NAMES:
        registry = registries.get(handler_name)
        if registry is None:
            continue
        config = getattr(registry, "handler_config", None)
        if config is not None and hasattr(config, "api_key"):
            setattr(config, "api_key", normalized_key)

        handler = getattr(registry, "handler", None)
        if handler_name == "HIWM" and handler is not None:
            # HIWM snapshots the credential during handler loading, so update
            # its in-memory copy before any new session context is created.
            setattr(handler, "_api_key", normalized_key)

    # ASR and TTS use the DashScope SDK's process-wide credential. Avoid a new
    # import here; their handler modules have already imported the SDK in the
    # real runtime, while lightweight unit tests need no DashScope dependency.
    dashscope_module = sys.modules.get("dashscope")
    if dashscope_module is not None:
        setattr(dashscope_module, "api_key", normalized_key)

    return build_public_api_config(handler_manager)
