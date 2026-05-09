from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


def _make_handler():
    """Return an httpx MockTransport handler for HuggingFace Chat flows."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        # Bootstrap: prime session
        if path == "/chat":
            return httpx.Response(200, text="<html>ok</html>")

        # Models list
        if path == "/chat/api/v2/models":
            return httpx.Response(
                200,
                json=[{"id": "meta-llama/Meta-Llama-3.1-70B-Instruct", "name": "Llama 3.1 70B"}],
            )

        # Create conversation
        if path == "/chat/conversation":
            return httpx.Response(200, json={"conversationId": "conv-hf-1"})

        # Get conversation messages (for root message id)
        if path == "/chat/api/v2/conversations/conv-hf-1":
            return httpx.Response(
                200,
                json={"messages": [{"id": "root-msg-1", "role": "system"}]},
            )

        # Streaming chat
        if path == "/chat/conversation/conv-hf-1":
            lines = [
                json.dumps({"type": "messageId", "messageId": "msg-1"}),
                json.dumps({"type": "stream", "token": "Hello "}),
                json.dumps({"type": "stream", "token": "from HF!"}),
                json.dumps({"type": "finalAnswer", "text": "Hello from HF!"}),
            ]
            body = "\n".join(lines) + "\n"
            return httpx.Response(200, text=body)

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    return handler


@pytest.mark.asyncio
async def test_huggingface_bootstrap_and_stream() -> None:
    bridge = LLMCookieBridge.create(
        "huggingface",
        cookies={"hf-chat": "test-cookie-value"},
        transport=httpx.MockTransport(_make_handler()),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert "HF" in response.text
    assert response.conversation_id == "conv-hf-1"
    assert response.message_id == "msg-1"


@pytest.mark.asyncio
async def test_huggingface_custom_model() -> None:
    bridge = LLMCookieBridge.create(
        "huggingface",
        cookies={"hf-chat": "test-cookie-value"},
        transport=httpx.MockTransport(_make_handler()),
    )
    async with bridge:
        response = await bridge.chat("Hello!", model="mistralai/Mixtral-8x7B-Instruct-v0.1")

    assert response.text == "Hello from HF!"
