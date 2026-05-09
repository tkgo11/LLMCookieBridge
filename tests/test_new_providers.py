"""Basic provider instantiation and registration tests for new providers."""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from llm_cookie_bridge.client import LLMCookieBridge, _PROVIDERS


ALL_EXPECTED_PROVIDERS = [
    "gemini",
    "chatgpt",
    "claude",
    "perplexity",
    "huggingface",
    "grok",
    "phind",
    "deepseek",
    "you",
    "pi",
    "meta",
    "mistral",
    "copilot",
]


def test_all_providers_registered():
    """All expected provider keys should be present in the registry."""
    for name in ALL_EXPECTED_PROVIDERS:
        assert name in _PROVIDERS, f"Provider '{name}' missing from registry"


def test_provider_count():
    """There should be at least 13 registered providers."""
    assert len(_PROVIDERS) >= 13


def test_grok_instantiation():
    bridge = LLMCookieBridge.create(
        "grok",
        cookies={"sso": "fake", "sso-rw": "fake"},
    )
    assert bridge.provider.provider_name == "grok"


def test_phind_instantiation_anonymous():
    bridge = LLMCookieBridge.create("phind")
    assert bridge.provider.provider_name == "phind"


def test_deepseek_instantiation():
    bridge = LLMCookieBridge.create("deepseek", auth_token="fake_token")
    assert bridge.provider.provider_name == "deepseek"
    # Token should be in auth_state
    assert bridge.provider._auth_state.get("auth_token") == "fake_token"


def test_you_instantiation_anonymous():
    bridge = LLMCookieBridge.create("you")
    assert bridge.provider.provider_name == "you"


def test_pi_instantiation():
    bridge = LLMCookieBridge.create("pi")
    assert bridge.provider.provider_name == "pi"


def test_meta_instantiation():
    bridge = LLMCookieBridge.create("meta")
    assert bridge.provider.provider_name == "meta"


def test_mistral_instantiation():
    bridge = LLMCookieBridge.create(
        "mistral",
        cookie_header="mistral-chat-session=fake_session",
    )
    assert bridge.provider.provider_name == "mistral"


def test_copilot_instantiation():
    bridge = LLMCookieBridge.create(
        "copilot",
        cookie_header="_U=fake_token",
    )
    assert bridge.provider.provider_name == "copilot"


def test_provider_base_urls():
    """Verify each new provider has a properly set default base URL."""
    expected_urls = {
        "grok": "https://grok.com",
        "phind": "https://www.phind.com",
        "deepseek": "https://chat.deepseek.com",
        "you": "https://you.com",
        "pi": "https://pi.ai",
        "meta": "https://www.meta.ai",
        "mistral": "https://chat.mistral.ai",
        "copilot": "https://copilot.microsoft.com",
    }
    for name, expected_url in expected_urls.items():
        cls = _PROVIDERS[name]
        assert cls.default_base_url == expected_url, (
            f"{name}: expected {expected_url}, got {cls.default_base_url}"
        )


def test_you_model_map():
    """YouProvider should have a non-empty MODEL_MAP."""
    from llm_cookie_bridge.providers.you import YouProvider
    assert len(YouProvider.MODEL_MAP) > 0
    assert "gpt-4o" in YouProvider.MODEL_MAP


def test_deepseek_default_model():
    from llm_cookie_bridge.providers.deepseek import DeepSeekProvider
    assert DeepSeekProvider.DEFAULT_MODEL == "deepseek_chat"
