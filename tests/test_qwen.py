"""Mock-transport tests for the Qwen Chat provider."""
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
async def test_qwen_stream_chat() -> None:
    chunks = [
        json.dumps({"choices": [{"delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None}]}),
        json.dumps({"choices": [{"delta": {"role": "assistant", "content": " Qwen!"}, "finish_reason": "stop"}]}),
    ]
    body = _sse(*chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer test-qwen-token" in request.headers.get("authorization", "")
        payload = json.loads(request.content)
        assert payload["model"] == "qwen-plus-latest"
        assert payload["stream"] is True
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "qwen",
        auth_token="test-qwen-token",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi!")

    assert response.text == "Hello Qwen!"
    assert response.provider == "qwen"


@pytest.mark.asyncio
async def test_qwen_custom_model_and_web_search() -> None:
    captured: list[dict] = []
    body = _sse(
        json.dumps({"choices": [{"delta": {"content": "result"}, "finish_reason": "stop"}]})
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "qwen",
        auth_token="tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Latest news?", model="qwen-max-latest", web_search=True)

    assert captured[0]["model"] == "qwen-max-latest"
    msg = captured[0]["messages"][0]
    assert msg["feature_config"]["web_search_enabled"] is True


def test_qwen_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "qwen",
        auth_token="test-qwen-token",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "qwen"


def test_qwen_default_model() -> None:
    from llm_cookie_bridge.providers.qwen import QwenProvider

    assert QwenProvider.DEFAULT_MODEL == "qwen-plus-latest"
