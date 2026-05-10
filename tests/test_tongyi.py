"""Mock-transport tests for the Tongyi Qianwen provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_tongyi_stream_chat() -> None:
    session_id = "sess-abc-123"
    msg_id = "msg-def-456"

    def handler(request: httpx.Request) -> httpx.Response:
        if "tongyi.aliyun.com" in str(request.url):
            return httpx.Response(200, text="<html>ok</html>")
        frames = [
            {
                "sessionId": session_id,
                "msgId": msg_id,
                "msgStatus": "ongoing",
                "contents": [
                    {
                        "contentType": "text",
                        "role": "assistant",
                        "content": "Hello from Tongyi!",
                    }
                ],
            },
            {
                "sessionId": session_id,
                "msgId": msg_id,
                "msgStatus": "finished",
                "contents": [
                    {
                        "contentType": "text",
                        "role": "assistant",
                        "content": "Hello from Tongyi!",
                    }
                ],
            },
        ]
        body = "\n".join(f"data: {json.dumps(f)}" for f in frames)
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "tongyi",
        cookies={"tongyi_sso_ticket": "fake-ticket"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello from Tongyi!"
    assert response.provider == "tongyi"
    assert response.conversation_id == session_id


@pytest.mark.asyncio
async def test_tongyi_requires_cookie() -> None:
    from llm_cookie_bridge.exceptions import AuthenticationError

    bridge = LLMCookieBridge.create(
        "tongyi",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")),
    )
    with pytest.raises((AuthenticationError, Exception)):
        async with bridge:
            await bridge.chat("Hello")


def test_tongyi_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "tongyi",
        cookies={"tongyi_sso_ticket": "fake-ticket"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "tongyi"
