"""Mock-transport tests for Together AI, Fireworks AI, Novita, SambaNova, and Cerebras."""
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


def _openai_chunk(content: str, finish_reason: str | None = None) -> str:
    return json.dumps({
        "id": "chatcmpl-test",
        "choices": [{"delta": {"content": content}, "finish_reason": finish_reason}],
    })


# ---------------------------------------------------------------------------
# Together AI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_together_registration() -> None:
    bridge = LLMCookieBridge.create(
        "together",
        auth_token="test-together-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "together"


@pytest.mark.asyncio
async def test_together_stream_chat() -> None:
    body = _sse(
        _openai_chunk("Together "),
        _openai_chunk("AI response!", "stop"),
    )

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
async def test_together_custom_model() -> None:
    captured: list[dict] = []
    body = _sse(_openai_chunk("ok", "stop"))

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


# ---------------------------------------------------------------------------
# Fireworks AI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fireworks_registration() -> None:
    bridge = LLMCookieBridge.create(
        "fireworks",
        auth_token="fw-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "fireworks"


@pytest.mark.asyncio
async def test_fireworks_stream_chat() -> None:
    body = _sse(
        _openai_chunk("Fireworks "),
        _openai_chunk("is fast!", "stop"),
    )

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
    body = _sse(_openai_chunk("done", "stop"))

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


# ---------------------------------------------------------------------------
# Novita AI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_novita_registration() -> None:
    bridge = LLMCookieBridge.create(
        "novita",
        auth_token="novita-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "novita"


@pytest.mark.asyncio
async def test_novita_stream_chat() -> None:
    body = _sse(
        _openai_chunk("Novita "),
        _openai_chunk("response!", "stop"),
    )

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


# ---------------------------------------------------------------------------
# SambaNova
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sambanova_registration() -> None:
    bridge = LLMCookieBridge.create(
        "sambanova",
        auth_token="sn-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "sambanova"


@pytest.mark.asyncio
async def test_sambanova_stream_chat() -> None:
    body = _sse(
        _openai_chunk("SambaNova "),
        _openai_chunk("speed!", "stop"),
    )

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
    body = _sse(_openai_chunk("reasoning", "stop"))

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


# ---------------------------------------------------------------------------
# Cerebras
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cerebras_registration() -> None:
    bridge = LLMCookieBridge.create(
        "cerebras",
        auth_token="cw-test-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "cerebras"


@pytest.mark.asyncio
async def test_cerebras_stream_chat() -> None:
    body = _sse(
        _openai_chunk("Cerebras "),
        _openai_chunk("is blazing fast!", "stop"),
    )

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
    body = _sse(_openai_chunk("done", "stop"))

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
