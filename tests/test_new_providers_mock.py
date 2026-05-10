"""Mock-transport tests for Grok, Phind, DeepSeek, You, Pi, Meta AI, Mistral, and Copilot providers."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


def _sse_body(*chunks_json: str, done: bool = True) -> str:
    """Build a well-formed SSE body from JSON strings.
    Each chunk is ``data: <json>\\n\\n`` (blank-line-separated).
    """
    parts = [f"data: {c}\n\n" for c in chunks_json]
    if done:
        parts.append("data: [DONE]\n\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Grok
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grok_bootstrap_and_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/rest/app-chat/conversations/new":
            chunks = [
                {"result": {"response": {"token": "Hello"}}},
                {"result": {"response": {"token": " Grok!"}}},
                {
                    "result": {
                        "response": {
                            "modelResponse": {
                                "message": "Hello Grok!",
                                "conversationId": "grok-conv-1",
                            }
                        }
                    }
                },
            ]
            body = "\n".join(json.dumps(c) for c in chunks) + "\n"
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "grok",
        cookies={"sso": "fake", "sso-rw": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hello!")

    assert response.text == "Hello Grok!"
    assert response.conversation_id == "grok-conv-1"


@pytest.mark.asyncio
async def test_grok_continues_existing_conversation() -> None:
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if "/rest/app-chat/conversations/existing-id/responses" in request.url.path:
            body = json.dumps({
                "result": {
                    "response": {
                        "modelResponse": {
                            "message": "continued",
                            "conversationId": "existing-id",
                        }
                    }
                }
            }) + "\n"
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "grok",
        cookies={"sso": "fake"},
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("follow up", conversation_id="existing-id")

    assert any("/rest/app-chat/conversations/existing-id/responses" in p for p in called_paths)
    assert response.text == "continued"


# ---------------------------------------------------------------------------
# Phind
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phind_anonymous_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " Phind!"}}]},
            {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
        ]
        body = _sse_body(*[json.dumps(c) for c in chunks])
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "phind",
        transport=httpx.MockTransport(handler),
        allow_custom_base_url=True,
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Hello Phind!"


@pytest.mark.asyncio
async def test_phind_with_session_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        chunks = [{"choices": [{"delta": {"content": "Authenticated!"}}]},
                  {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]}]
        body = _sse_body(*[json.dumps(c) for c in chunks])
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "phind",
        cookies={"next-auth.session-token": "fake-token"},
        transport=httpx.MockTransport(handler),
        allow_custom_base_url=True,
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Authenticated!"


# ---------------------------------------------------------------------------
# DeepSeek
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deepseek_creates_session_and_streams() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v0/chat_session/create":
            return httpx.Response(200, json={"data": {"biz_data": {"id": "ds-session-1"}}})
        if request.url.path == "/api/v0/chat/completion":
            chunks = [
                {"choices": [{"delta": {"content": "Hello", "type": "text"}}]},
                {"choices": [{"delta": {"content": " DeepSeek!", "type": "text"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse_body(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "deepseek",
        auth_token="fake-bearer-token",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello DeepSeek!"
    assert response.conversation_id == "ds-session-1"
    assert "POST /api/v0/chat_session/create" in calls
    assert "POST /api/v0/chat/completion" in calls


@pytest.mark.asyncio
async def test_deepseek_reuses_existing_session() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/v0/chat/completion":
            body = _sse_body(json.dumps({"choices": [{"delta": {"content": "ok", "type": "text"}}]}))
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "deepseek",
        auth_token="tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hi", conversation_id="existing-session")

    assert "/api/v0/chat_session/create" not in calls
    assert response.text == "ok"


@pytest.mark.asyncio
async def test_deepseek_thinking_chunks_are_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v0/chat_session/create":
            return httpx.Response(200, json={"data": {"biz_data": {"id": "s1"}}})
        if request.url.path == "/api/v0/chat/completion":
            chunks = [
                {"choices": [{"delta": {"content": "<thinking>reasoning...</thinking>", "type": "thinking"}}]},
                {"choices": [{"delta": {"content": "Final answer", "type": "text"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse_body(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "deepseek",
        auth_token="tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("think about it", thinking_enabled=True)

    assert "thinking" not in response.text.lower()
    assert response.text == "Final answer"


# ---------------------------------------------------------------------------
# You.com
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_you_anonymous_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/streamingSearch":
            body = (
                "event: youChatToken\n"
                'data: {"youChatToken": "Hello"}\n\n'
                "event: youChatToken\n"
                'data: {"youChatToken": " You!"}\n\n'
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "you",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello You!"


@pytest.mark.asyncio
async def test_you_custom_model_sets_chat_mode() -> None:
    sent_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/streamingSearch":
            for key, val in request.url.params.items():
                sent_params[key] = val
            body = 'event: youChatToken\ndata: {"youChatToken": "custom"}\n\n'
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "you",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("hello", model="gpt-4o")

    assert sent_params.get("selectedChatMode") == "custom"
    assert sent_params.get("selectedAiModel") == "gpt_4o"


# ---------------------------------------------------------------------------
# Pi.ai
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pi_starts_conversation_and_streams() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/chat/start":
            return httpx.Response(200, json={"conversations": [{"sid": "pi-conv-1"}]})
        if request.url.path == "/api/chat":
            body = (
                'data: {"text": "Hello"}\n'
                'data: {"text": " Pi!"}\n'
            )
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "pi",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi Pi!")

    assert response.text == "Hello Pi!"
    assert response.conversation_id == "pi-conv-1"
    assert "POST /api/chat/start" in calls
    assert "POST /api/chat" in calls


@pytest.mark.asyncio
async def test_pi_reuses_existing_conversation() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/chat/start":
            return httpx.Response(200, json={"conversations": [{"sid": "new-conv"}]})
        if request.url.path == "/api/chat":
            body = 'data: {"text": "response"}\n'
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "pi",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("Hi!", conversation_id="existing-conv")

    assert response.conversation_id == "existing-conv"


# ---------------------------------------------------------------------------
# Meta AI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_anonymous_tos_and_stream() -> None:
    """Test Meta AI with anonymous access where TOS acceptance fails gracefully,
    falling back to the www.meta.ai graphql endpoint (mockable)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            html = (
                '"LSD",[],{"token":"lsd-token"}'
                '"DTSGInitialData",[],{"token":"dtsg-token"}'
                '"abra_csrf":{"value":"csrf-token"}'
                '"datr":{"value":"datr-token"}'
                '"_js_datr":{"value":"js-datr"}'
            )
            return httpx.Response(200, text=html)
        if request.url.path == "/api/graphql/":
            body = request.content.decode()
            if "useAbraAcceptTOSForTempUserMutation" in body:
                # Simulate TOS acceptance failure → access_token stays None
                return httpx.Response(400, text="error")
            if "useAbraSendMessageMutation" in body:
                line1 = json.dumps({
                    "data": {
                        "node": {
                            "bot_response_message": {
                                "streaming_state": "STREAMING",
                                "snippet": "Hello Meta!",
                            }
                        }
                    }
                })
                line2 = json.dumps({
                    "data": {
                        "node": {
                            "bot_response_message": {
                                "streaming_state": "OVERALL_DONE",
                                "snippet": "Hello Meta!",
                                "fetch_id": None,
                            }
                        }
                    }
                })
                return httpx.Response(200, text=line1 + "\n" + line2 + "\n")
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "meta",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert "Hello" in response.text


@pytest.mark.asyncio
async def test_meta_token_extraction() -> None:
    """Verify LSD/DTSG token extraction from page HTML."""
    from llm_cookie_bridge.providers.meta import MetaAIProvider
    import re

    provider = MetaAIProvider()
    html = (
        '"LSD",[],{"token":"my-lsd-value"}'
        '"DTSGInitialData",[],{"token":"my-dtsg-value"}'
    )
    lsd_m = provider._LSD_PATTERN.search(html)
    dtsg_m = provider._DTSG_PATTERN.search(html)
    assert lsd_m and lsd_m.group(1) == "my-lsd-value"
    assert dtsg_m and dtsg_m.group(1) == "my-dtsg-value"
    await provider.close()


# ---------------------------------------------------------------------------
# Mistral Le Chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mistral_creates_conversation_and_streams() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/chat/new":
            return httpx.Response(200, json={"id": "mistral-conv-1"})
        if request.url.path == "/api/chat":
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " Mistral!"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse_body(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "mistral",
        cookie_header="mistral-chat-session=fake",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello Mistral!"
    assert response.conversation_id == "mistral-conv-1"
    assert "POST /api/chat/new" in calls
    assert "POST /api/chat" in calls


@pytest.mark.asyncio
async def test_mistral_reuses_conversation() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/api/chat":
            body = _sse_body(json.dumps({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}))
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "mistral",
        cookie_header="session=fake",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hi", conversation_id="existing-conv")

    assert "/api/chat/new" not in calls
    assert response.text == "ok"


# ---------------------------------------------------------------------------
# Microsoft Copilot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_copilot_bootstrap_and_stream() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/c/api/chat":
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " Copilot!"}}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ]
            body = _sse_body(*[json.dumps(c) for c in chunks])
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "copilot",
        cookie_header="_U=fake-token",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hello Copilot!"
    assert "GET /" in calls
    assert "POST /c/api/chat" in calls


@pytest.mark.asyncio
async def test_copilot_tone_option() -> None:
    sent_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<html>ok</html>")
        if request.url.path == "/c/api/chat":
            sent_payload.update(json.loads(request.content))
            body = _sse_body(json.dumps({"choices": [{"delta": {"content": "creative"}}]}))
            return httpx.Response(200, text=body)
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "copilot",
        cookie_header="_U=tok",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        await bridge.chat("be creative", tone="Creative")

    assert sent_payload.get("tone") == "Creative"
