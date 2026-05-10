"""Mock-transport tests for the Groq provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


def _sse(*chunks: str, done: bool = True) -> str:
    parts = [f"data: {c}\n\n" for c in chunks]
    if done:
        parts.append("data: [DONE]\n\n")
    return "".join(parts)


@pytest.mark.asyncio
async def test_groq_stream_chat() -> None:
    chunks = [
        json.dumps({"id": "chatcmpl-1", "choices": [{"delta": {"content": "Fast"}, "finish_reason": None}]}),
        json.dumps({"id": "chatcmpl-1", "choices": [{"delta": {"content": " answer!"}, "finish_reason": "stop"}]}),
    ]
    body = _sse(*chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer gsk_test123" in request.headers.get("authorization", "")
        assert request.url.path == "/openai/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "llama-3.3-70b-versatile"
        assert payload["stream"] is True
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "groq",
        auth_token="gsk_test123",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("What is 2+2?")

    assert response.text == "Fast answer!"
    assert response.provider == "groq"


@pytest.mark.asyncio
async def test_groq_custom_model_and_system() -> None:
    captured: list[dict] = []
    body = _sse(
        json.dumps({"id": "x", "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "groq",
        auth_token="gsk_abc",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Explain AI", model="mixtral-8x7b-32768", system="Be brief.")

    assert captured[0]["model"] == "mixtral-8x7b-32768"
    messages = captured[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "Be brief."
    assert messages[1]["role"] == "user"


def test_groq_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "groq",
        auth_token="gsk_test123",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "groq"


def test_groq_default_model() -> None:
    from llm_cookie_bridge.providers.groq import GroqProvider

    assert GroqProvider.DEFAULT_MODEL == "llama-3.3-70b-versatile"
