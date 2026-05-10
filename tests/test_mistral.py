"""Mock-transport tests for the Mistral Le Chat provider."""
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
async def test_mistral_creates_conversation_and_streams() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/chat/new":
            return httpx.Response(200, json={"id": "mistral-conv-1"})
        if request.url.path == "/api/chat":
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " Mistral!"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "mistral",
        cookie_header="mistral-chat-session=fake",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello Mistral!"
    assert response.conversation_id == "mistral-conv-1"
    assert "POST /api/chat/new" in calls
    assert "POST /api/chat" in calls


@pytest.mark.asyncio
async def test_mistral_reuses_conversation() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/chat":
            body = _sse(
                json.dumps(
                    {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}
                )
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "mistral",
        cookie_header="session=fake",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hi", conversation_id="existing-conv")

    assert "/api/chat/new" not in calls
    assert response.text == "ok"


def test_mistral_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "mistral",
        cookie_header="mistral-chat-session=fake_session",
    )
    assert bridge.provider.provider_name == "mistral"


def test_mistral_default_model() -> None:
    from llm_cookie_bridge.providers.mistral import MistralProvider

    assert MistralProvider.DEFAULT_MODEL == "mistral-large-latest"
