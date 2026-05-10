"""Mock-transport tests for the Cohere provider."""
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
async def test_cohere_stream_chat() -> None:
    chunks = [
        json.dumps({"type": "content-delta", "index": 0, "delta": {"text": "Hello"}}),
        json.dumps({"type": "content-delta", "index": 0, "delta": {"text": " world"}}),
        json.dumps({"type": "message-end", "finish_reason": "COMPLETE", "usage": {}}),
    ]
    body = _sse(*chunks, done=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer test-cohere-key" in request.headers.get("authorization", "")
        assert request.url.path == "/v2/chat"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "cohere",
        auth_token="test-cohere-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello world"
    assert response.provider == "cohere"


@pytest.mark.asyncio
async def test_cohere_with_preamble_and_web_search() -> None:
    captured: list[dict] = []
    chunks = [
        json.dumps({"type": "content-delta", "index": 0, "delta": {"text": "Answer"}}),
        json.dumps({"type": "message-end", "finish_reason": "COMPLETE"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=_sse(*chunks, done=False))

    bridge = LLMCookieBridge.create(
        "cohere",
        auth_token="key123",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat(
            "What is AI?",
            preamble="You are a concise helper.",
            web_search=True,
            model="command-r",
        )

    assert captured[0]["preamble"] == "You are a concise helper."
    assert captured[0]["connectors"] == [{"id": "web-search"}]
    assert captured[0]["model"] == "command-r"


@pytest.mark.asyncio
async def test_cohere_requires_auth_token() -> None:
    from llm_cookie_bridge.exceptions import AuthenticationError

    bridge = LLMCookieBridge.create(
        "cohere",
        transport=httpx.MockTransport(lambda r: httpx.Response(401, text="unauthorized")),
    )
    with pytest.raises((AuthenticationError, Exception)):
        async with bridge:
            await bridge.chat("Hello")


def test_cohere_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "cohere",
        auth_token="test-cohere-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "cohere"


def test_cohere_default_model() -> None:
    from llm_cookie_bridge.providers.cohere import CohereProvider

    assert CohereProvider.DEFAULT_MODEL == "command-r-plus"
