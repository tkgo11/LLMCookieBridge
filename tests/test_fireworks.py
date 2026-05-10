"""Mock-transport tests for the Fireworks AI provider."""
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
async def test_fireworks_stream_chat() -> None:
    body = _sse(_chunk("Fireworks "), _chunk("is fast!", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer fw-test-key" in request.headers.get("authorization", "")
        assert request.url.path == "/inference/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "accounts/fireworks/models/llama-v3p3-70b-instruct"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "fireworks",
        auth_token="fw-test-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Fireworks is fast!"
    assert response.provider == "fireworks"


@pytest.mark.asyncio
async def test_fireworks_custom_model() -> None:
    captured: list[dict] = []
    body = _sse(_chunk("done", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "fireworks",
        auth_token="fw-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Tell me about AI", model="accounts/fireworks/models/deepseek-v3")

    assert captured[0]["model"] == "accounts/fireworks/models/deepseek-v3"


def test_fireworks_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "fireworks",
        auth_token="fw-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "fireworks"


def test_fireworks_default_model() -> None:
    from llm_cookie_bridge.providers.fireworks import FireworksProvider

    assert FireworksProvider.DEFAULT_MODEL == "accounts/fireworks/models/llama-v3p3-70b-instruct"
