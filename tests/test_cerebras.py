"""Mock-transport tests for the Cerebras Inference provider."""
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
async def test_cerebras_stream_chat() -> None:
    body = _sse(_chunk("Cerebras "), _chunk("is blazing fast!", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer cw-test-key" in request.headers.get("authorization", "")
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "llama3.1-70b"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "cerebras",
        auth_token="cw-test-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("How fast are you?")

    assert response.text == "Cerebras is blazing fast!"
    assert response.provider == "cerebras"


@pytest.mark.asyncio
async def test_cerebras_custom_model_and_system() -> None:
    captured: list[dict] = []
    body = _sse(_chunk("done", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "cerebras",
        auth_token="key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("What is AI?", model="llama3.1-8b", system="You are brief.")

    assert captured[0]["model"] == "llama3.1-8b"
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["messages"][0]["content"] == "You are brief."
    assert captured[0]["messages"][1]["role"] == "user"


def test_cerebras_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "cerebras",
        auth_token="cw-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "cerebras"


def test_cerebras_default_model() -> None:
    from llm_cookie_bridge.providers.cerebras import CerebrasProvider

    assert CerebrasProvider.DEFAULT_MODEL == "llama3.1-70b"
