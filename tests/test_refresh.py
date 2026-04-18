from __future__ import annotations

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_refresh_callback_runs_on_initial_authentication_failure() -> None:
    attempts = {"session": 0}

    async def refresh_callback(provider_name: str) -> dict[str, str]:
        assert provider_name == "chatgpt"
        return {"__Secure-next-auth.session-token": "fresh-cookie"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/session":
            attempts["session"] += 1
            cookie = request.headers.get("cookie", "")
            if "fresh-cookie" in cookie:
                return httpx.Response(200, json={"accessToken": "jwt-token"})
            return httpx.Response(401, json={"detail": "expired"})
        if request.url.path == "/backend-api/conversation":
            body = (
                'data: {"conversation_id":"conv-1","message":{"id":"msg-1","author":{"role":"assistant"},"content":{"parts":["Hello"]},"metadata":{"finish_details":{"type":"stop"}},"end_turn":true}}\n\n'
                'data: [DONE]\n\n'
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "chatgpt",
        cookies={"__Secure-next-auth.session-token": "stale-cookie"},
        refresh_callback=refresh_callback,
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello"
    assert attempts["session"] == 2
