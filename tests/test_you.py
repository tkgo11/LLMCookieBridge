"""Mock-transport tests for the You.com provider."""
from __future__ import annotations

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_you_anonymous_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/streamingSearch":
            body = (
                "event: youChatToken\n"
                'data: {"youChatToken": "Hello"}\n\n'
                "event: youChatToken\n"
                'data: {"youChatToken": " You!"}\n\n'
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "you",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello You!"


@pytest.mark.asyncio
async def test_you_custom_model_sets_chat_mode() -> None:
    sent_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/streamingSearch":
            for key, val in request.url.params.items():
                sent_params[key] = val
            body = 'event: youChatToken\ndata: {"youChatToken": "custom"}\n\n'
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "you",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("hello", model="gpt-4o")

    assert sent_params.get("selectedChatMode") == "custom"
    assert sent_params.get("selectedAiModel") == "gpt_4o"


def test_you_instantiation_anonymous() -> None:
    bridge = LLMCookieBridge.create("you")
    assert bridge.provider.provider_name == "you"


def test_you_model_map() -> None:
    from llm_cookie_bridge.providers.you import YouProvider

    assert len(YouProvider.MODEL_MAP) > 0
    assert "gpt-4o" in YouProvider.MODEL_MAP
