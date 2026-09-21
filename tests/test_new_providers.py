"""Mock-transport coverage for the expanded provider set.

Each provider is exercised through ``LLMCookieBridge.create`` + ``chat()``
against a mock transport that returns a provider-appropriate stream body.
"""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge
from llm_cookie_bridge.client import _PROVIDERS

OAI = 'data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": "stop"}]}\n\ndata: [DONE]\n\n'
TXT = 'data: {"text": "Hello"}\n\ndata: [DONE]\n\n'
CNT = 'data: {"content": "Hello"}\n\ndata: [DONE]\n\n'


def _params():
    return [
        # name, kwargs, body
        ("openrouter", {"auth_token": "t"}, OAI),
        ("groq", {"auth_token": "t"}, OAI),
        ("together", {"auth_token": "t"}, OAI),
        ("githubmodels", {"auth_token": "t"}, OAI),
        ("websim", {"auth_token": "t"}, OAI),
        ("sensechat", {"auth_token": "t"}, OAI),
        ("hailuo", {"auth_token": "t"}, TXT),
        ("chatglm", {"auth_token": "t"}, TXT),
        ("kimi", {"auth_token": "t"}, TXT),
        ("zai", {"auth_token": "t"}, OAI),
        ("cohere", {"auth_token": "t"}, 'data: {"type": "content-delta", "delta": {"message": {"content": {"text": "Hello"}}}}\n\n'),
        ("cody", {"auth_token": "t"}, 'data: {"completion": "Hello"}\n\n'),
        ("doubao", {"cookies": {"sessionid": "x"}}, TXT),
        ("yuanbao", {"cookies": {"tgw": "x"}}, CNT),
        ("sparkdesk", {"cookies": {"sso": "x"}}, TXT),
        ("monica", {"cookies": {"s": "x"}}, TXT),
        ("sider", {"cookies": {"s": "x"}}, TXT),
        ("merlin", {"cookies": {"s": "x"}}, TXT),
        ("popai", {"cookies": {"s": "x"}}, TXT),
        ("genspark", {"cookies": {"s": "x"}}, TXT),
        ("skywork", {"cookies": {"s": "x"}}, TXT),
        ("baichuan", {"cookies": {"s": "x"}}, TXT),
        ("ai360", {"cookies": {"s": "x"}}, TXT),
        ("wrtn", {"cookies": {"s": "x"}}, TXT),
        ("coze", {"cookies": {"s": "x"}}, TXT),
        ("kagi", {"cookies": {"s": "x"}}, TXT),
        ("lumo", {"cookies": {"s": "x"}}, TXT),
        ("v0", {"cookies": {"s": "x"}}, '{"type": "text-delta", "textDelta": "Hello"}\n'),
        ("lovable", {"cookies": {"s": "x"}}, TXT),
        ("abacus", {"cookies": {"s": "x"}}, TXT),
        ("aistudio", {"cookies": {"s": "x"}}, '{"text": "Hello"}\n'),
        ("notebooklm", {"cookies": {"s": "x"}}, '{"text": "Hello"}\n'),
        ("iask", {}, TXT),
        ("komo", {}, TXT),
        ("andi", {}, TXT),
        ("felo", {}, TXT),
        ("devv", {}, TXT),
        ("deepai", {}, TXT),
        ("lmarena", {}, TXT),
        ("venice", {}, '{"kind": "response", "content": "Hello"}\n'),
        ("scira", {}, '0:"Hello"\n'),
        ("bolt", {}, '{"type": "text-delta", "textDelta": "Hello"}\n'),
    ]


@pytest.mark.parametrize("name,kwargs,body", _params(), ids=[p[0] for p in _params()])
@pytest.mark.asyncio
async def test_new_provider_chat(name, kwargs, body):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        name,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )
    async with bridge:
        response = await bridge.chat("Hi")

    assert response.provider == name
    assert "Hello" in response.text


@pytest.mark.parametrize("name,kwargs,body", _params(), ids=[p[0] for p in _params()])
def test_new_provider_instantiation(name, kwargs, body):
    bridge = LLMCookieBridge.create(
        name,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="")),
        **kwargs,
    )
    assert bridge.provider.provider_name == name
    assert bridge.provider.default_base_url.startswith("https://")


@pytest.mark.asyncio
async def test_duckai_handshake_and_chat() -> None:
    """DuckAI must fetch the x-vqd-4 token before chatting."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/duckchat/v1/status":
            return httpx.Response(200, headers={"x-vqd-4": "vqd-token-1"})
        assert request.headers.get("x-vqd-4") == "vqd-token-1"
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-4o-mini"
        return httpx.Response(
            200,
            text='data: {"choices": [{"delta": {"content": "Hi there"}, "finish_reason": "stop"}]}\n\ndata: [DONE]\n\n',
            headers={"x-vqd-4": "vqd-token-2"},
        )

    bridge = LLMCookieBridge.create(
        "duckai",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert response.text == "Hi there"
    assert bridge.provider._auth_state["vqd"] == "vqd-token-2"


@pytest.mark.asyncio
async def test_zai_guest_fallback() -> None:
    """Zai works without a token via the guest endpoint fallback."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auths/guest":
            return httpx.Response(200, json={"data": {"token": "guest-jwt"}})
        if request.url.path == "/api/v2/chats/new":
            return httpx.Response(200, json={"data": {"id": "zc-1"}})
        return httpx.Response(
            200,
            text='data: {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}\n\ndata: [DONE]\n\n',
        )

    bridge = LLMCookieBridge.create("zai", transport=httpx.MockTransport(handler))
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "ok"
    assert bridge.provider._auth_state["auth_token"] == "guest-jwt"


@pytest.mark.asyncio
async def test_kimi_two_step_flow() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"id": "kimi-chat-1"})
        return httpx.Response(200, text='data: {"text": "yo"}\n\n')

    bridge = LLMCookieBridge.create(
        "kimi", auth_token="t", transport=httpx.MockTransport(handler)
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "yo"
    assert "/api/chat/kimi-chat-1/completion/stream" in seen


@pytest.mark.asyncio
async def test_scira_data_protocol() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='0:"Hel"\n0:"lo"\n')

    bridge = LLMCookieBridge.create("scira", transport=httpx.MockTransport(handler))
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Hello"


@pytest.mark.asyncio
async def test_venice_jsonl() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "outerface.venice.ai" in str(request.url)
        return httpx.Response(
            200,
            text='{"kind": "response", "content": "Ven"}\n{"kind": "response", "content": "ice"}\n',
        )

    bridge = LLMCookieBridge.create("venice", transport=httpx.MockTransport(handler))
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Venice"


AUTH_REQUIRED = [
    "openrouter", "groq", "together", "githubmodels", "websim", "sensechat",
    "hailuo", "chatglm", "kimi", "cody", "doubao", "yuanbao", "sparkdesk",
    "monica", "sider", "merlin", "popai", "genspark", "skywork", "baichuan",
    "ai360", "wrtn", "coze", "kagi", "lumo", "v0", "lovable", "abacus",
    "aistudio", "notebooklm",
]


@pytest.mark.parametrize("name", AUTH_REQUIRED)
@pytest.mark.asyncio
async def test_missing_auth_raises(name):
    """Providers that require credentials must fail fast without them."""
    import pytest as _pytest

    from llm_cookie_bridge.exceptions import AuthenticationError

    bridge = LLMCookieBridge.create(
        name, transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )
    with _pytest.raises(AuthenticationError):
        async for _ in bridge.stream("hi"):
            pass


@pytest.mark.asyncio
async def test_malformed_sse_events_skipped() -> None:
    """Broken JSON lines and non-text events must not crash the stream."""
    body = (
        "data: {not json\n\n"
        'data: {"unrelated": true}\n\n'
        "garbage line\n\n"
        'data: {"text": "good"}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "komo", transport=httpx.MockTransport(handler)
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "good"


@pytest.mark.asyncio
async def test_empty_stream_yields_done() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="data: [DONE]\n\n")

    bridge = LLMCookieBridge.create(
        "lmarena", transport=httpx.MockTransport(handler)
    )
    chunks = []
    async with bridge:
        async for chunk in bridge.stream("hi"):
            chunks.append(chunk)

    assert chunks[-1].done is True
    assert chunks[-1].text == ""


def test_every_provider_module_registered() -> None:
    """Every providers/*.py module must be registered under its provider_name."""
    import importlib
    import pkgutil

    import llm_cookie_bridge.providers as providers_pkg

    for mod_info in pkgutil.iter_modules(providers_pkg.__path__):
        mod_name = mod_info.name
        if mod_name in ("base", "_common"):
            continue
        module = importlib.import_module(f"llm_cookie_bridge.providers.{mod_name}")
        provider_classes = [
            obj for obj in vars(module).values()
            if isinstance(obj, type)
            and hasattr(obj, "provider_name")
            and obj.__module__ == module.__name__
        ]
        assert provider_classes, f"{mod_name}: no provider class found"
        cls = provider_classes[0]
        assert _PROVIDERS.get(cls.provider_name) is cls, (
            f"{cls.provider_name!r} not registered or mismatched"
        )


@pytest.mark.asyncio
async def test_cohere_v2_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "command-a-03-2025"
        body = (
            'data: {"type": "content-delta", "delta": {"message": {"content": {"text": "Co"}}}}\n\n'
            'data: {"type": "content-delta", "delta": {"message": {"content": {"text": "here"}}}}\n\n'
        )
        return httpx.Response(200, text=body)

    bridge = LLMCookieBridge.create(
        "cohere", auth_token="t", transport=httpx.MockTransport(handler)
    )
    async with bridge:
        response = await bridge.chat("hi")

    assert response.text == "Cohere"
