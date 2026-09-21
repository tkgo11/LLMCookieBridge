"""Mock-transport tests for the Tongyi Qianwen provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import AuthenticationError, LLMCookieBridge


def _sse(*chunks: str, done: bool = True) -> str:
    parts = [f"data: {c}\n\n" for c in chunks]
    if done:
        parts.append("data: [DONE]\n\n")
    return "".join(parts)


@pytest.mark.asyncio
async def test_tongyi_stream_chat() -> None:
    chunks = [
        json.dumps({"choices": [{"delta": {"content": "Hello from "}, "finish_reason": None}]}),
        json.dumps({"choices": [{"delta": {"content": "Tongyi!"}, "finish_reason": "stop"}]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer ty-tok" in request.headers.get("authorization", "")
        if request.url.path == "/api/v2/chats/new":
            return httpx.Response(200, json={"data": {"id": "ty-chat-1"}})
        assert request.url.path == "/api/v2/chat/completions"
        assert "chat_id=ty-chat-1" in str(request.url)
        return httpx.Response(200, text=_sse(*chunks))

    bridge = LLMCookieBridge.create(
        "tongyi",
        auth_token="ty-tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello from Tongyi!"
    assert response.provider == "tongyi"
    assert response.conversation_id == "ty-chat-1"


@pytest.mark.asyncio
async def test_tongyi_requires_token() -> None:
    bridge = LLMCookieBridge.create(
        "tongyi",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")),
    )
    with pytest.raises(AuthenticationError, match="requires an auth_token"):
        async with bridge:
            await bridge.chat("Hello")


def test_tongyi_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "tongyi",
        auth_token="ty-tok",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "tongyi"
