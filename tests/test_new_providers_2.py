"""Mock-transport tests for Poe, Blackbox AI, and Character.AI providers."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


# ---------------------------------------------------------------------------
# Poe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poe_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "poe",
        cookies={"p-b": "fake-pb", "p-lat": "fake-plat"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")),
    )
    assert bridge.provider.provider_name == "poe"


@pytest.mark.asyncio
async def test_poe_stream_chat() -> None:
    call_log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(request.url.path)

        # Formkey fetch from homepage
        if request.url.path == "/":
            return httpx.Response(
                200,
                text='<html><script>{"formkey":"testfkey1234567890123456"}</script></html>',
            )

        # GQL endpoint
        if request.url.path == "/api/gql_POST":
            body = json.loads(request.content)
            query_name = body.get("queryName", "")

            if query_name == "SubscriptionsMutation":
                return httpx.Response(200, json={"data": {"subscribe": True}})

            if query_name == "SendMessageMutation":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "messageEdgeCreate": {
                                "status": "success",
                                "chat": {
                                    "chatCode": "testcode123",
                                    "chatId": 99999,
                                    "id": "Q2hhdDo5OTk5OQ==",
                                    "title": "Test Chat",
                                },
                            }
                        }
                    },
                )

            if query_name == "ChatPageQuery":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "chatOfCode": {
                                "chatId": 99999,
                                "chatCode": "testcode123",
                                "title": "Test Chat",
                                "messagesConnection": {
                                    "edges": [
                                        {
                                            "node": {
                                                "author": "human",
                                                "text": "Hello",
                                                "messageId": 1,
                                                "state": "complete",
                                            }
                                        },
                                        {
                                            "node": {
                                                "author": "gpt4_o",
                                                "text": "Hello! How can I help?",
                                                "messageId": 2,
                                                "state": "complete",
                                            }
                                        },
                                    ]
                                },
                            }
                        }
                    },
                )

        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "poe",
        cookies={"p-b": "fake-pb", "p-lat": "fake-plat"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello! How can I help?"
    assert response.provider == "poe"


@pytest.mark.asyncio
async def test_poe_with_custom_formkey() -> None:
    """Poe provider should use provided formkey without fetching."""
    called = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        if request.url.path == "/api/gql_POST":
            body = json.loads(request.content)
            query_name = body.get("queryName", "")
            if query_name == "SubscriptionsMutation":
                return httpx.Response(200, json={"data": {}})
            if query_name == "SendMessageMutation":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "messageEdgeCreate": {
                                "status": "success",
                                "chat": {
                                    "chatCode": "abc",
                                    "chatId": 1,
                                    "id": "x",
                                    "title": "t",
                                },
                            }
                        }
                    },
                )
            if query_name == "ChatPageQuery":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "chatOfCode": {
                                "chatId": 1,
                                "title": "t",
                                "messagesConnection": {
                                    "edges": [
                                        {
                                            "node": {
                                                "author": "gpt4_o",
                                                "text": "poe response",
                                                "messageId": 10,
                                                "state": "complete",
                                            }
                                        }
                                    ]
                                },
                            }
                        }
                    },
                )
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "poe",
        cookies={"p-b": "x", "p-lat": "y"},
        formkey="myfakeformkey",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi")

    # Should NOT have fetched the homepage (formkey already provided)
    assert "/" not in called
    assert response.text == "poe response"


# ---------------------------------------------------------------------------
# Blackbox AI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blackbox_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake-session"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")),
    )
    assert bridge.provider.provider_name == "blackbox"


@pytest.mark.asyncio
async def test_blackbox_stream_chat_plain_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>homepage</html>")
        if request.url.path == "/api/chat":
            return httpx.Response(200, text="The answer to your question is 42.")
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake-session"},
        validated="00f37b34-a166-4efb-bce5-1312d87f2f94",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("What is the answer?")

    assert response.text == "The answer to your question is 42."
    assert response.provider == "blackbox"


@pytest.mark.asyncio
async def test_blackbox_stream_chat_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>home</html>")
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={"response": "JSON response from Blackbox!"},
            )
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello?")

    assert response.text == "JSON response from Blackbox!"


@pytest.mark.asyncio
async def test_blackbox_with_agent_model() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html/>")
        if request.url.path == "/api/chat":
            captured.append(json.loads(request.content))
            return httpx.Response(200, text="DeepSeek response")
        return httpx.Response(200, text="ok")

    bridge = LLMCookieBridge.create(
        "blackbox",
        cookies={"sessionId": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Tell me about AI", model="deepseek-v3")

    assert response.text == "DeepSeek response"
    assert captured[0]["agentMode"]["id"] == "deepseek-chat"


# ---------------------------------------------------------------------------
# Character.AI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_characterai_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "characterai",
        auth_token="fake-token",
        character_id="test-char-id",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    assert bridge.provider.provider_name == "characterai"


@pytest.mark.asyncio
async def test_characterai_stream_chat() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # User info (refresh)
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
        # Existing chats
        if "chats/" in str(request.url) and request.method == "GET":
            return httpx.Response(200, json={"chats": [{"chat_id": "existing-chat-1"}]})
        # Send message
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
    from llm_cookie_bridge.exceptions import AuthenticationError

    bridge = LLMCookieBridge.create(
        "characterai",
        transport=httpx.MockTransport(lambda r: httpx.Response(401, text="unauthorized")),
        allow_custom_base_url=True,
    )
    with pytest.raises((AuthenticationError, Exception)):
        async with bridge:
            await bridge.chat("Hello")
