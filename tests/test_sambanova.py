"""Mock-transport tests for the SambaNova Cloud provider."""
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
async def test_sambanova_stream_chat() -> None:
    body = _sse(_chunk("SambaNova "), _chunk("speed!", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer sn-test-key" in request.headers.get("authorization", "")
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "Meta-Llama-3.3-70B-Instruct"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "sambanova",
        auth_token="sn-test-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "SambaNova speed!"
    assert response.provider == "sambanova"


@pytest.mark.asyncio
async def test_sambanova_deepseek_model() -> None:
    captured: list[dict] = []
    body = _sse(_chunk("reasoning", "stop"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "sambanova",
        auth_token="key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Solve this", model="DeepSeek-R1")

    assert captured[0]["model"] == "DeepSeek-R1"


def test_sambanova_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "sambanova",
        auth_token="sn-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "sambanova"


def test_sambanova_default_model() -> None:
    from llm_cookie_bridge.providers.sambanova import SambanovaProvider

    assert SambanovaProvider.DEFAULT_MODEL == "Meta-Llama-3.3-70B-Instruct"
