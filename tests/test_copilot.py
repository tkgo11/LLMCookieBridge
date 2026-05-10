"""Mock-transport tests for the Microsoft Copilot provider."""
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
async def test_copilot_bootstrap_and_stream() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/c/api/chat":
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " Copilot!"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "copilot",
        cookie_header="_U=fake-token",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello Copilot!"
    assert "GET /" in calls
    assert "POST /c/api/chat" in calls


@pytest.mark.asyncio
async def test_copilot_tone_option() -> None:
    sent_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/c/api/chat":
            sent_payload.update(json.loads(request.content))
            body = _sse(json.dumps({"choices": [{"delta": {"content": "creative"}}]}))
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "copilot",
        cookie_header="_U=tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("be creative", tone="Creative")

    assert sent_payload.get("tone") == "Creative"


def test_copilot_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "copilot",
        cookie_header="_U=fake_token",
    )
    assert bridge.provider.provider_name == "copilot"
