"""Validate the local DeepSeek key without printing it or persisting a reply."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

api_key = os.getenv("LLM_API_KEY", "").strip()
base_url = os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com").rstrip("/")
model = os.getenv("LLM_MODEL", "deepseek-v4-flash").strip()

if not api_key:
    raise SystemExit("LLM_API_KEY is empty. Paste the DeepSeek key into HIWM/.env first.")
if model != "deepseek-v4-flash":
    raise SystemExit(f"LLM_MODEL must be deepseek-v4-flash, got {model!r}.")

try:
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)
    available = {item.id for item in client.models.list().data}
    if model not in available:
        raise SystemExit(f"DeepSeek authenticated, but {model} is not available to this account.")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with OK only."}],
        max_tokens=8,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise SystemExit("DeepSeek returned an empty completion.")
except OpenAIError as exc:
    raise SystemExit(f"DeepSeek connection failed ({type(exc).__name__}).") from exc

print(f"DeepSeek connection passed: model={response.model or model}")
