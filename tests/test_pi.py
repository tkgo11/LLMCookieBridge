"""Mock-transport tests for the Pi.ai provider."""
from __future__ import annotations

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_pi_starts_conversation_and_streams() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/chat/start":
            return httpx.Response(200, json={"conversations": [{"sid": "pi-conv-1"}]})
        if request.url.path == "/api/chat":
            body = 'data: {"text": "Hello"}\ndata: {"text": " Pi!"}\n'
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "pi",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi Pi!")

    assert response.text == "Hello Pi!"
    assert response.conversation_id == "pi-conv-1"
    assert "POST /api/chat/start" in calls
    assert "POST /api/chat" in calls


@pytest.mark.asyncio
async def test_pi_reuses_existing_conversation() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/chat/start":
            return httpx.Response(200, json={"conversations": [{"sid": "new-conv"}]})
        if request.url.path == "/api/chat":
            body = 'data: {"text": "response"}\n'
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "pi",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi!", conversation_id="existing-conv")

    assert response.conversation_id == "existing-conv"


def test_pi_instantiation() -> None:
    bridge = LLMCookieBridge.create("pi")
    assert bridge.provider.provider_name == "pi"
