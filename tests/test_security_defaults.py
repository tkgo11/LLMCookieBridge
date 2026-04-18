from __future__ import annotations

import pytest

from llm_cookie_bridge import LLMCookieBridge


def test_cross_host_base_url_override_is_rejected() -> None:
    with pytest.raises(ValueError):
        LLMCookieBridge.create("chatgpt", base_url="https://evil.example")


def test_reserved_headers_are_rejected() -> None:
    with pytest.raises(ValueError):
        LLMCookieBridge.create("claude", headers={"Authorization": "Bearer nope"})


def test_same_host_https_override_is_allowed() -> None:
    bridge = LLMCookieBridge.create("gemini", base_url="https://gemini.google.com")
    assert bridge.provider.base_url == "https://gemini.google.com"
