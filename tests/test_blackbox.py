"""Mock-transport tests for the Blackbox AI provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_blackbox_stream_chat_plain_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>homepage</html>")
        if request.url.path == "/api/chat":
            return httpx.Response(200, text="The answer to your question is 42.")
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake-session"},
        validated="00f37b34-a166-4efb-bce5-1312d87f2f94",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("What is the answer?")

    assert response.text == "The answer to your question is 42."
    assert response.provider == "blackbox"


@pytest.mark.asyncio
async def test_blackbox_stream_chat_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>home</html>")
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"response": "JSON response from Blackbox!"})
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello?")

    assert response.text == "JSON response from Blackbox!"


@pytest.mark.asyncio
async def test_blackbox_with_agent_model() -> None:
    """Agent model aliases must resolve to the correct agentMode id."""
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html/>")
        if request.url.path == "/api/chat":
            captured.append(json.loads(request.content))
            return httpx.Response(200, text="DeepSeek response")
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Tell me about AI", model="deepseek-v3")

    assert response.text == "DeepSeek response"
    assert captured[0]["agentMode"]["id"] == "deepseek-chat"


def test_blackbox_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake-session"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")),
    )
    assert bridge.provider.provider_name == "blackbox"


def test_blackbox_default_model() -> None:
    from llm_cookie_bridge.providers.blackbox import BlackboxProvider

    assert BlackboxProvider.DEFAULT_MODEL == "blackboxai"
