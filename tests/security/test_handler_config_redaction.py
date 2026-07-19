from __future__ import annotations

import traceback
from typing import Dict, Optional

from loguru import logger
from pydantic import Field

from chat_engine.common.handler_base import (
    HandlerBase,
    HandlerBaseInfo,
    HandlerDetail,
)
from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.contexts.session_context import SessionContext
from chat_engine.core.handler_manager import HandlerManager
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.chat_engine_config_data import (
    ChatEngineConfigModel,
    HandlerBaseConfigModel,
)


class SensitiveConfig(HandlerBaseConfigModel):
    api_key: str = Field(repr=True)
    access_token: str = Field(repr=True)
    model_name: str = "safe-model"


class DummyHandler(HandlerBase):
    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(config_model=SensitiveConfig)

    def load(
        self,
        engine_config: ChatEngineConfigModel,
        handler_config: Optional[HandlerBaseConfigModel] = None,
    ):
        return None

    def create_context(
        self,
        session_context: SessionContext,
        handler_config: Optional[HandlerBaseConfigModel] = None,
    ) -> HandlerContext:
        return HandlerContext(session_context.session_info.session_id)

    def start_context(
        self, session_context: SessionContext, handler_context: HandlerContext
    ):
        return None

    def get_handler_detail(
        self, session_context: SessionContext, context: HandlerContext
    ) -> HandlerDetail:
        return HandlerDetail(inputs={}, outputs={})

    def handle(
        self,
        context: HandlerContext,
        inputs: ChatData,
        output_definitions: Dict[ChatDataType, object],
    ):
        return None

    def destroy_context(self, context: HandlerContext):
        return None


class DummyEngine:
    pass


def test_handler_registration_log_omits_config_and_credentials():
    api_key = "unit-test-api-key-value"
    access_token = "unit-test-access-token-value"
    manager = HandlerManager(DummyEngine())
    manager.handler_configs["Sensitive"] = {
        "module": "unit/test",
        "api_key": api_key,
        "access_token": access_token,
        "model_name": "safe-model",
    }
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}", level="INFO")
    try:
        manager.register_handler("Sensitive", DummyHandler())
    finally:
        logger.remove(sink_id)

    registration_log = "".join(messages)
    assert "Registered handler Sensitive" in registration_log
    assert api_key not in registration_log
    assert access_token not in registration_log
    assert "api_key" not in registration_log
    assert "access_token" not in registration_log


def test_handler_config_repr_filters_sensitive_fields_even_if_repr_enabled():
    config = SensitiveConfig(
        api_key="repr-api-key-value",
        access_token="repr-access-token-value",
    )
    rendered = repr(config)
    assert "repr-api-key-value" not in rendered
    assert "repr-access-token-value" not in rendered
    assert "safe-model" in rendered


def test_handler_validation_failure_does_not_expose_rejected_secret():
    secret = "invalid-secret-must-never-escape"
    manager = HandlerManager(DummyEngine())
    manager.handler_configs["Sensitive"] = {
        "module": "unit/test",
        "api_key": secret,
        "access_token": "valid-token",
        "concurrent_limit": "not-an-integer",
    }
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}", level="ERROR")
    try:
        try:
            manager.register_handler("Sensitive", DummyHandler())
        except ValueError as error:
            error_message = str(error)
            rendered_error = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
        else:
            raise AssertionError("invalid handler config was unexpectedly accepted")
    finally:
        logger.remove(sink_id)

    assert error_message == "Invalid configuration for handler Sensitive"
    assert secret not in rendered_error
    assert secret not in "".join(messages)
