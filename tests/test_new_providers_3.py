"""Mock-transport tests for Cohere, Groq, Qwen, and Tongyi providers."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


def _sse(*chunks: str, done: bool = True) -> str:
    parts = [f"data: {c}\n\n" for c in chunks]
    if done:
        parts.append("data: [DONE]\n\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Cohere
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cohere_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "cohere",
        auth_token="test-cohere-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "cohere"


@pytest.mark.asyncio
async def test_cohere_stream_chat() -> None:
    chunks = [
        json.dumps({"type": "content-delta", "index": 0, "delta": {"text": "Hello"}}),
        json.dumps({"type": "content-delta", "index": 0, "delta": {"text": " world"}}),
        json.dumps({"type": "message-end", "finish_reason": "COMPLETE", "usage": {}}),
    ]
    body = _sse(*chunks, done=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer test-cohere-key" in request.headers.get("authorization", "")
        assert request.url.path == "/v2/chat"
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "cohere",
        auth_token="test-cohere-key",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello world"
    assert response.provider == "cohere"


@pytest.mark.asyncio
async def test_cohere_with_preamble_and_web_search() -> None:
    captured: list[dict] = []
    chunks = [
        json.dumps({"type": "content-delta", "index": 0, "delta": {"text": "Answer"}}),
        json.dumps({"type": "message-end", "finish_reason": "COMPLETE"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=_sse(*chunks, done=False))

    bridge = LLMCookieBridge.create(
        "cohere",
        auth_token="key123",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat(
            "What is AI?",
            preamble="You are a concise helper.",
            web_search=True,
            model="command-r",
        )

    assert response.text == "Answer"
    assert captured[0]["preamble"] == "You are a concise helper."
    assert captured[0]["connectors"] == [{"id": "web-search"}]
    assert captured[0]["model"] == "command-r"


@pytest.mark.asyncio
async def test_cohere_requires_auth_token() -> None:
    from llm_cookie_bridge.exceptions import AuthenticationError

    bridge = LLMCookieBridge.create(
        "cohere",
        transport=httpx.MockTransport(lambda r: httpx.Response(401, text="unauthorized")),
    )
    with pytest.raises((AuthenticationError, Exception)):
        async with bridge:
            await bridge.chat("Hello")


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groq_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "groq",
        auth_token="gsk_test123",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "groq"


@pytest.mark.asyncio
async def test_groq_stream_chat() -> None:
    chunks = [
        json.dumps({"id": "chatcmpl-1", "choices": [{"delta": {"content": "Fast"}, "finish_reason": None}]}),
        json.dumps({"id": "chatcmpl-1", "choices": [{"delta": {"content": " answer!"}, "finish_reason": "stop"}]}),
    ]
    body = _sse(*chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer gsk_test123" in request.headers.get("authorization", "")
        assert request.url.path == "/openai/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "llama-3.3-70b-versatile"
        assert payload["stream"] is True
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "groq",
        auth_token="gsk_test123",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("What is 2+2?")

    assert response.text == "Fast answer!"
    assert response.provider == "groq"


@pytest.mark.asyncio
async def test_groq_custom_model_and_system() -> None:
    captured: list[dict] = []
    body = _sse(
        json.dumps({"id": "x", "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "groq",
        auth_token="gsk_abc",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Explain AI", model="mixtral-8x7b-32768", system="Be brief.")

    assert captured[0]["model"] == "mixtral-8x7b-32768"
    messages = captured[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "Be brief."
    assert messages[1]["role"] == "user"


# ---------------------------------------------------------------------------
# Qwen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qwen_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "qwen",
        auth_token="test-qwen-token",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "qwen"


@pytest.mark.asyncio
async def test_qwen_stream_chat() -> None:
    chunks = [
        json.dumps({"choices": [{"delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None}]}),
        json.dumps({"choices": [{"delta": {"role": "assistant", "content": " Qwen!"}, "finish_reason": "stop"}]}),
    ]
    body = _sse(*chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Bearer test-qwen-token" in request.headers.get("authorization", "")
        payload = json.loads(request.content)
        assert payload["model"] == "qwen-plus-latest"
        assert payload["stream"] is True
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "qwen",
        auth_token="test-qwen-token",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi!")

    assert response.text == "Hello Qwen!"
    assert response.provider == "qwen"


@pytest.mark.asyncio
async def test_qwen_custom_model_and_web_search() -> None:
    captured: list[dict] = []
    body = _sse(
        json.dumps({"choices": [{"delta": {"content": "result"}, "finish_reason": "stop"}]})
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "qwen",
        auth_token="tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("Latest news?", model="qwen-max-latest", web_search=True)

    assert captured[0]["model"] == "qwen-max-latest"
    msg = captured[0]["messages"][0]
    assert msg["feature_config"]["web_search_enabled"] is True


# ---------------------------------------------------------------------------
# Tongyi
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tongyi_registration_and_instantiation() -> None:
    bridge = LLMCookieBridge.create(
        "tongyi",
        cookies={"tongyi_sso_ticket": "fake-ticket"},
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
    )
    assert bridge.provider.provider_name == "tongyi"


@pytest.mark.asyncio
async def test_tongyi_stream_chat() -> None:
    session_id = "sess-abc-123"
    msg_id = "msg-def-456"

    def handler(request: httpx.Request) -> httpx.Response:
        if "tongyi.aliyun.com" in str(request.url):
            return httpx.Response(200, text="<html>ok</html>")
        # Chat endpoint
        frames = [
            {
                "sessionId": session_id,
                "msgId": msg_id,
                "msgStatus": "ongoing",
                "contents": [
                    {"contentType": "text", "role": "assistant", "content": "Hello from Tongyi!"}
                ],
            },
            {
                "sessionId": session_id,
                "msgId": msg_id,
                "msgStatus": "finished",
                "contents": [
                    {"contentType": "text", "role": "assistant", "content": "Hello from Tongyi!"}
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
