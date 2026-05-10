"""Mock-transport tests for the DeepSeek provider."""
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
async def test_deepseek_creates_session_and_streams() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v0/chat_session/create":
            return httpx.Response(200, json={"data": {"biz_data": {"id": "ds-session-1"}}})
        if request.url.path == "/api/v0/chat/completion":
            chunks = [
                {"choices": [{"delta": {"content": "Hello", "type": "text"}}]},
                {"choices": [{"delta": {"content": " DeepSeek!", "type": "text"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "deepseek",
        auth_token="fake-bearer-token",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello DeepSeek!"
    assert response.conversation_id == "ds-session-1"
    assert "POST /api/v0/chat_session/create" in calls
    assert "POST /api/v0/chat/completion" in calls


@pytest.mark.asyncio
async def test_deepseek_reuses_existing_session() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/v0/chat/completion":
            body = _sse(json.dumps({"choices": [{"delta": {"content": "ok", "type": "text"}}]}))
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "deepseek",
        auth_token="tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hi", conversation_id="existing-session")

    assert "/api/v0/chat_session/create" not in calls
    assert response.text == "ok"


@pytest.mark.asyncio
async def test_deepseek_thinking_chunks_are_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v0/chat_session/create":
            return httpx.Response(200, json={"data": {"biz_data": {"id": "s1"}}})
        if request.url.path == "/api/v0/chat/completion":
            chunks = [
                {"choices": [{"delta": {"content": "<thinking>reasoning...</thinking>", "type": "thinking"}}]},
                {"choices": [{"delta": {"content": "Final answer", "type": "text"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "deepseek",
        auth_token="tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("think about it", thinking_enabled=True)

    assert "thinking" not in response.text.lower()
    assert response.text == "Final answer"


def test_deepseek_instantiation() -> None:
    bridge = LLMCookieBridge.create("deepseek", auth_token="fake_token")
    assert bridge.provider.provider_name == "deepseek"
    assert bridge.provider._auth_state.get("auth_token") == "fake_token"


def test_deepseek_default_model() -> None:
    from llm_cookie_bridge.providers.deepseek import DeepSeekProvider

    assert DeepSeekProvider.DEFAULT_MODEL == "deepseek_chat"
