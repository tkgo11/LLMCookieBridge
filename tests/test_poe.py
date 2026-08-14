"""Mock-transport tests for the Poe provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import AuthenticationError, LLMCookieBridge


@pytest.mark.asyncio
async def test_poe_bootstrap_and_stream() -> None:
    call_log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(request.url.path)

        if request.url.path == "/":
            return httpx.Response(
                200,
                text='<html><script>{"formkey":"testfkey1234567890123456"}</script></html>',
            )

        if request.url.path == "/api/gql_POST":
            body = json.loads(request.content)
            query_name = body.get("queryName", "")

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
async def test_poe_with_custom_formkey_skips_homepage() -> None:
    """When formkey is provided, Poe must not fetch the homepage."""
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        if request.url.path == "/api/gql_POST":
            body = json.loads(request.content)
            query_name = body.get("queryName", "")
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

    assert "/" not in called
    assert response.text == "poe response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cookies",
    [{}, {"p-b": "fake-pb"}, {"p-lat": "fake-plat"}],
)
async def test_poe_requires_both_session_cookies(cookies: dict[str, str]) -> None:
    """Missing either required browser-session cookie must fail before I/O."""

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected network request: {request.url}")

    bridge = LLMCookieBridge.create(
        "poe",
        cookies=cookies,
        formkey="manual-formkey",
        transport=httpx.MockTransport(unexpected_request),
    )
    async with bridge:
        with pytest.raises(AuthenticationError, match="requires p-b and p-lat cookies"):
            await bridge.refresh()


def test_poe_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "poe",
        cookies={"p-b": "fake-pb", "p-lat": "fake-plat"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")),
    )
    assert bridge.provider.provider_name == "poe"
