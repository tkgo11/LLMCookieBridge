from __future__ import annotations

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_claude_discovers_org_creates_chat_and_streams() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/organizations":
            return httpx.Response(200, json=[{"uuid": "org-1"}])
        if request.url.path == "/api/organizations/org-1/chat_conversations":
            return httpx.Response(201, json={"uuid": "chat-1"})
        if request.url.path == "/api/organizations/org-1/chat_conversations/chat-1/completion":
            body = 'data: {"completion":"Hello from Claude"}\n\n'
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "claude",
        cookie_header="sessionKey=abc",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Hello from Claude"
    assert response.conversation_id == "chat-1"
