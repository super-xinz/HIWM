"""Local-only OpenAI-compatible server used by manual integration smoke tests."""

from __future__ import annotations

import json
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse


app = FastAPI()


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "deepseek-v4-flash", "object": "model", "owned_by": "deepseek"}
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    content = "我听到了。我们可以先把这个重要决定拆成最关键的一步。"
    if body.get("stream"):
        async def events():
            for text in ("我听到了。", "我们可以先把这个重要决定", "拆成最关键的一步。"):
                chunk = {
                    "id": "mock-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": body.get("model", "mock-model"),
                    "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(events(), media_type="text/event-stream")
    return {
        "id": "mock-completion",
        "object": "chat.completion",
        "created": 0,
        "model": body.get("model", "mock-model"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("MOCK_LLM_PORT", "18001")))
