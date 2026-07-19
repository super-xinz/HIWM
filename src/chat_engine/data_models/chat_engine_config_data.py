from typing import Dict, Optional, List, Union

from pydantic import BaseModel, Field

from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.engine_channel_type import EngineChannelType


class HandlerBaseConfigModel(BaseModel):
    enabled: bool = Field(default=True)
    module: Optional[str] = Field(default=None)
    concurrent_limit: int = Field(default=1)
    # Type override configuration for duplex mode
    # Format: {"ORIGINAL_TYPE_NAME": "TARGET_TYPE_NAME"}
    # Example: {"HUMAN_AUDIO": "HUMAN_DUPLEX_AUDIO"}
    input_type_override: Optional[Dict[str, str]] = Field(default=None)
    output_type_override: Optional[Dict[str, str]] = Field(default=None)

    def __repr_args__(self):
        """Exclude credential-shaped fields from every handler config repr.

        This is a second line of defence for diagnostics outside
        ``HandlerManager``.  It deliberately keeps non-secret fields such as
        ``max_tokens`` and ``api_key_env`` visible.
        """
        sensitive_names = {
            "api_key",
            "token",
            "secret",
            "password",
            "authorization",
            "credential",
            "credentials",
            "private_key",
            "access_token",
            "auth_token",
            "client_secret",
        }
        sensitive_suffixes = (
            "_api_key",
            "_access_token",
            "_auth_token",
            "_secret",
            "_password",
            "_credential",
            "_credentials",
            "_private_key",
        )
        for field_name, value in super().__repr_args__():
            normalized = field_name.lower().replace("-", "_")
            if normalized in sensitive_names or normalized.endswith(sensitive_suffixes):
                continue
            yield field_name, value


class LogicBaseConfigModel(BaseModel):
    enabled: bool = Field(default=True)
    module: Optional[str] = Field(default=None)


class ChatEngineOutputSource(BaseModel):
    handler: Optional[Union[str, List[str]]]
    type: ChatDataType


class ChatEngineConfigModel(BaseModel):
    model_root: str = ""
    concurrent_limit: int = Field(default=1)
    handler_search_path: List[str] = Field(default_factory=list)
    logic_search_path: List[str] = Field(default_factory=list)
    handler_configs: Optional[Dict[str, Dict]] = None
    logic_configs: Optional[Dict[str, Dict]] = Field(default=None)
    outputs: Dict[EngineChannelType, ChatEngineOutputSource] = Field(default_factory=dict)
    turn_config: Optional[Dict] = Field(default=None)
