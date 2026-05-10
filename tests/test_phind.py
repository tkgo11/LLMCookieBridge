"""Mock-transport tests for the Phind provider."""
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
async def test_phind_anonymous_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " Phind!"}}]},
            {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
        ]
        body = _sse(*[json.dumps(c) for c in chunks])
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "phind",
        transport=httpx.MockTransport(handler),
        allow_custom_base_url=True,
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Hello Phind!"


@pytest.mark.asyncio
async def test_phind_with_session_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        chunks = [
            {"choices": [{"delta": {"content": "Authenticated!"}}]},
            {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
        ]
        body = _sse(*[json.dumps(c) for c in chunks])
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "phind",
        cookies={"next-auth.session-token": "fake-token"},
        transport=httpx.MockTransport(handler),
        allow_custom_base_url=True,
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Authenticated!"


def test_phind_instantiation_anonymous() -> None:
    bridge = LLMCookieBridge.create("phind")
    assert bridge.provider.provider_name == "phind"


def test_phind_default_model() -> None:
    from llm_cookie_bridge.providers.phind import PhindProvider

    assert PhindProvider.DEFAULT_MODEL == "Phind-70B"
