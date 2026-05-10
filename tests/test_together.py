"""Mock-transport tests for the Together AI provider."""
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


def _chunk(content: str, finish_reason: str | None = None) -> str:
    return json.dumps(
        {"id": "chatcmpl-test", "choices": [{"delta": {"content": content}, "finish_reason": finish_reason}]}
    )


@pytest.mark.asyncio
async def test_together_stream_chat() -> None:
    body = _sse(_chunk("Together "), _chunk("AI response!", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer test-together-key" in request.headers.get("authorization", "")
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "together",
        auth_token="test-together-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Together AI response!"
    assert response.provider == "together"


@pytest.mark.asyncio
async def test_together_custom_model_and_system() -> None:
    captured: list[dict] = []
    body = _sse(_chunk("ok", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "together",
        auth_token="key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Hi", model="Qwen/Qwen3-235B-A22B", system="Be concise.")

    assert captured[0]["model"] == "Qwen/Qwen3-235B-A22B"
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["messages"][0]["content"] == "Be concise."


def test_together_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "together",
        auth_token="test-together-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "together"


def test_together_default_model() -> None:
    from llm_cookie_bridge.providers.together import TogetherProvider

    assert TogetherProvider.DEFAULT_MODEL == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
