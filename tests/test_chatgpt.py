from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_chatgpt_cookie_bootstrap_and_stream() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/auth/session":
            return httpx.Response(200, json={"accessToken": "jwt-token"})
        if request.url.path == "/backend-api/conversation":
            body = (
                "data: "
                + json.dumps(
                    {
                        "conversation_id": "conv-1",
                        "message": {
                            "id": "msg-1",
                            "author": {"role": "assistant"},
                            "content": {"parts": ["Hello"]},
                            "metadata": {"finish_details": {"type": "stop"}},
                            "end_turn": True,
                        },
                    }
                )
                + "\n\n"
                + "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "chatgpt",
        cookies={"__Secure-next-auth.session-token": "cookie"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello"
    assert response.conversation_id == "conv-1"
    assert calls == ["GET /api/auth/session", "POST /backend-api/conversation"]


@pytest.mark.asyncio
async def test_chatgpt_reuses_last_message_id_for_follow_up_turns() -> None:
    parent_ids: list[str | None] = []
    responses = iter(
        [
            {
                "conversation_id": "conv-1",
                "message": {
                    "id": "msg-1",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Hello"]},
                    "metadata": {"finish_details": {"type": "stop"}},
                    "end_turn": True,
                },
            },
            {
                "conversation_id": "conv-1",
                "message": {
                    "id": "msg-2",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Back again"]},
                    "metadata": {"finish_details": {"type": "stop"}},
                    "end_turn": True,
                },
            },
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/session":
            return httpx.Response(200, json={"accessToken": "jwt-token"})
        if request.url.path == "/backend-api/conversation":
            payload = json.loads(request.content.decode())
            parent_ids.append(payload.get("parent_message_id"))
            body = "data: " + json.dumps(next(responses)) + "\n\n" + "data: [DONE]\n\n"
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "chatgpt",
        cookies={"__Secure-next-auth.session-token": "cookie"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("hello")
        await bridge.chat("follow up")

    assert parent_ids[0] is not None
    assert parent_ids[1] == "msg-1"
