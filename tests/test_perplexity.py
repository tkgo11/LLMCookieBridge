from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_perplexity_sse_answer_extraction() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/session":
            return httpx.Response(200, json={"user": {"id": "u1"}})
        if request.url.path == "/rest/sse/perplexity_ask":
            final_answer = json.dumps({"answer": "Perplexity says hi", "chunks": []})
            message = {
                "backend_uuid": "backend-1",
                "text": json.dumps([
                    {"step_type": "SEARCH", "content": {}},
                    {"step_type": "FINAL", "content": {"answer": final_answer}},
                ]),
            }
            body = (
                "event: message\n"
                f"data: {json.dumps(message)}\n\n"
                "event: end_of_stream\n"
                "data: done\n\n"
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "perplexity",
        cookies={"__Secure-next-auth.session-token": "token"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Perplexity says hi"
    assert response.conversation_id == "backend-1"
