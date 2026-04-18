from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_gemini_bootstrap_and_parse_stream_frames() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/app":
            html = "\n".join(
                [
                    '"SNlM0e": "access-token"',
                    '"cfb2h": "build-label"',
                    '"FdrFJe": "session-id"',
                    '"TuX5cc": "en"',
                ]
            )
            return httpx.Response(200, text=html)
        if request.url.path.endswith("/StreamGenerate"):
            part_json = [None, ["cid-1", "rid-1"], None, None, [["candidate-1", ["Hello Gemini"]]]]
            frame_json = json.dumps([[None, None, json.dumps(part_json)]])
            body = f"{len(frame_json)}\n{frame_json}\n"
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "gemini",
        cookies={"__Secure-1PSID": "psid", "__Secure-1PSIDTS": "psidts"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello Gemini"
    assert response.conversation_id == "cid-1"
