"""Mock-transport tests for the Novita AI provider."""
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
async def test_novita_stream_chat() -> None:
    body = _sse(_chunk("Novita "), _chunk("response!", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer novita-test-key" in request.headers.get("authorization", "")
        assert request.url.path == "/v3/openai/chat/completions"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "novita",
        auth_token="novita-test-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Novita response!"
    assert response.provider == "novita"


@pytest.mark.asyncio
async def test_novita_custom_model_and_system() -> None:
    captured: list[dict] = []
    body = _sse(_chunk("done", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "novita",
        auth_token="key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Explain AI", model="meta-llama/llama-3.1-8b-instruct", system="Be brief.")

    assert captured[0]["model"] == "meta-llama/llama-3.1-8b-instruct"
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["messages"][1]["role"] == "user"


def test_novita_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "novita",
        auth_token="novita-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "novita"


def test_novita_default_model() -> None:
    from llm_cookie_bridge.providers.novita import NovitaProvider

    assert NovitaProvider.DEFAULT_MODEL == "meta-llama/llama-3.3-70b-instruct"
