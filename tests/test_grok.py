"""Mock-transport tests for the Grok provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_grok_bootstrap_and_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/rest/app-chat/conversations/new":
            chunks = [
                {"result": {"response": {"token": "Hello"}}},
                {"result": {"response": {"token": " Grok!"}}},
                {
                    "result": {
                        "response": {
                            "modelResponse": {
                                "message": "Hello Grok!",
                                "conversationId": "grok-conv-1",
                            }
                        }
                    }
                },
            ]
            body = "\n".join(json.dumps(c) for c in chunks) + "\n"
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "grok",
        cookies={"sso": "fake", "sso-rw": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello Grok!"
    assert response.conversation_id == "grok-conv-1"


@pytest.mark.asyncio
async def test_grok_continues_existing_conversation() -> None:
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if "/rest/app-chat/conversations/existing-id/responses" in request.url.path:
            body = (
                json.dumps(
                    {
                        "result": {
                            "response": {
                                "modelResponse": {
                                    "message": "continued",
                                    "conversationId": "existing-id",
                                }
                            }
                        }
                    }
                )
                + "\n"
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "grok",
        cookies={"sso": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("follow up", conversation_id="existing-id")

    assert any(
        "/rest/app-chat/conversations/existing-id/responses" in p for p in called_paths
    )
    assert response.text == "continued"


def test_grok_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "grok",
        cookies={"sso": "fake", "sso-rw": "fake"},
    )
    assert bridge.provider.provider_name == "grok"


def test_grok_default_model() -> None:
    from llm_cookie_bridge.providers.grok import GrokProvider

    assert GrokProvider.DEFAULT_MODEL == "grok-3"
