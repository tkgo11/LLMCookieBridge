"""Mock-transport tests for the Blackbox AI provider."""
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
async def test_blackbox_stream_chat() -> None:
    chunks = [
        json.dumps({"id": "cmpl-1", "choices": [{"delta": {"content": "The answer"}, "finish_reason": None}]}),
        json.dumps({"id": "cmpl-1", "choices": [{"delta": {"content": " is 42."}, "finish_reason": "stop"}]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        assert "Bearer test-bb-key" in request.headers.get("authorization", "")
        payload = json.loads(request.content)
        assert payload["model"] == "blackboxai/openai/gpt-4o"
        assert payload["stream"] is True
        return httpx.Response(200, text=_sse(*chunks))

    bridge = LLMCookieBridge.create(
        "blackbox",
        auth_token="test-bb-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("What is the answer?")

    assert response.text == "The answer is 42."
    assert response.provider == "blackbox"


@pytest.mark.asyncio
async def test_blackbox_custom_model() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            text=_sse(json.dumps({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})),
        )

    bridge = LLMCookieBridge.create(
        "blackbox",
        auth_token="k",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Hi", model="blackboxai/deepseek/deepseek-chat")

    assert captured[0]["model"] == "blackboxai/deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_blackbox_requires_key() -> None:
    bridge = LLMCookieBridge.create(
        "blackbox",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    with pytest.raises(AuthenticationError, match="requires an API key"):
        async with bridge:
            await bridge.chat("Hi")


def test_blackbox_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "blackbox",
        auth_token="k",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "blackbox"


def test_blackbox_default_model() -> None:
    from llm_cookie_bridge.providers.blackbox import BlackboxProvider

    assert BlackboxProvider.DEFAULT_MODEL == "blackboxai/openai/gpt-4o"
