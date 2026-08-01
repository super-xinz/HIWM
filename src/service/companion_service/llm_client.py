from __future__ import annotations

from collections.abc import AsyncIterator

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from .config import CompanionSettings


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: CompanionSettings):
        self.settings = settings

    def _client(self) -> AsyncOpenAI:
        if not self.settings.llm_configured:
            raise LLMError("大模型服务尚未配置")
        return AsyncOpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_api_base_url,
            timeout=self.settings.llm_timeout_seconds,
        )

    async def chat(self, messages: list[dict[str, str]]) -> tuple[str, str]:
        try:
            response = await self._client().chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=0.65,
                max_tokens=600,
                stream=False,
            )
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise LLMError("大模型返回了空内容")
            return content.strip(), response.model or self.settings.llm_model
        except LLMError:
            raise
        except (APIConnectionError, APIStatusError, APITimeoutError, IndexError) as exc:
            raise LLMError("大模型暂时无法生成回复") from exc

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        try:
            stream = await self._client().chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=0.65,
                max_tokens=600,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except (APIConnectionError, APIStatusError, APITimeoutError) as exc:
            raise LLMError("大模型流式连接中断") from exc
