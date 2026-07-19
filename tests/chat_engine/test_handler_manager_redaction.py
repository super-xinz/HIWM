from chat_engine.core.handler_manager import _redact_config


def test_redact_config_hides_nested_credentials():
    source = {
        "api_key": "sk-real-secret",
        "nested": {
            "access_token": "token-value",
            "model_name": "qwen-omni-turbo-realtime",
        },
        "items": [{"password": "do-not-log"}],
    }

    redacted = _redact_config(source)

    assert redacted["api_key"] == "<redacted>"
    assert redacted["nested"]["access_token"] == "<redacted>"
    assert redacted["nested"]["model_name"] == "qwen-omni-turbo-realtime"
    assert redacted["items"][0]["password"] == "<redacted>"
    assert "sk-real-secret" not in repr(redacted)
