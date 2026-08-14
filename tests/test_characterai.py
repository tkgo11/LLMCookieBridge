"""Mock-transport tests for the Character.AI provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import AuthenticationError, LLMCookieBridge


@pytest.mark.asyncio
async def test_characterai_stream_chat() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "plus.character.ai/chat/user" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "user": {
                        "user": {
                            "id": "12345",
                            "username": "testuser",
                            "name": "Test User",
                        }
                    }
                },
            )
        if "chats/" in str(request.url) and request.method == "GET":
            return httpx.Response(200, json={"chats": [{"chat_id": "existing-chat-1"}]})
        if "turn/candidate" in str(request.url):
            frames = [
                {
                    "turn": {
                        "author": {"is_human": False, "name": "Char"},
                        "candidates": [
                            {
                                "candidate_id": "cand-1",
                                "raw_content": "Hello there!",
                                "is_final": False,
                            }
                        ],
                        "primary_candidate_id": "cand-1",
                    }
                },
                {
                    "turn": {
                        "author": {"is_human": False, "name": "Char"},
                        "candidates": [
                            {
                                "candidate_id": "cand-1",
                                "raw_content": "Hello there! How are you?",
                                "is_final": True,
                            }
                        ],
                        "primary_candidate_id": "cand-1",
                    }
                },
            ]
            body = "\n".join(json.dumps(f) for f in frames)
            return httpx.Response(200, text=body)
        return httpx.Response(200, json={})

    bridge = LLMCookieBridge.create(
        "characterai",
        auth_token="fake-token",
        character_id="test-char-123",
        transport=httpx.MockTransport(handler),
        allow_custom_base_url=True,
    )
    async with bridge:
        response = await bridge.chat("Hi!")

    assert response.text == "Hello there! How are you?"
    assert response.provider == "characterai"
    assert response.conversation_id == "existing-chat-1"


@pytest.mark.asyncio
async def test_characterai_requires_auth_token() -> None:
    bridge = LLMCookieBridge.create(
        "characterai",
        transport=httpx.MockTransport(lambda r: httpx.Response(401, text="unauthorized")),
        allow_custom_base_url=True,
    )
    with pytest.raises(AuthenticationError, match="requires an auth_token"):
        async with bridge:
            await bridge.chat("Hello")


def test_characterai_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "characterai",
        auth_token="fake-token",
        character_id="test-char-id",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    assert bridge.provider.provider_name == "characterai"
