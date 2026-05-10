"""Provider registry and cross-provider sanity checks."""
from __future__ import annotations

from llm_cookie_bridge.client import LLMCookieBridge, _PROVIDERS

EXPECTED_PROVIDERS = [
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
    "poe",
    "blackbox",
    "characterai",
    "cohere",
    "groq",
    "qwen",
    "tongyi",
    "together",
    "fireworks",
    "novita",
    "sambanova",
    "cerebras",
]


def test_all_providers_registered() -> None:
    for name in EXPECTED_PROVIDERS:
        assert name in _PROVIDERS, f"Provider '{name}' missing from registry"


def test_provider_count() -> None:
    assert len(_PROVIDERS) >= len(EXPECTED_PROVIDERS)


def test_provider_base_urls() -> None:
    expected_urls = {
        "gemini": "https://gemini.google.com",
        "chatgpt": "https://chatgpt.com",
        "claude": "https://claude.ai",
        "perplexity": "https://www.perplexity.ai",
        "huggingface": "https://huggingface.co",
        "grok": "https://grok.com",
        "phind": "https://www.phind.com",
        "deepseek": "https://chat.deepseek.com",
        "you": "https://you.com",
        "pi": "https://pi.ai",
        "meta": "https://www.meta.ai",
        "mistral": "https://chat.mistral.ai",
        "copilot": "https://copilot.microsoft.com",
        "poe": "https://poe.com",
        "blackbox": "https://www.blackbox.ai",
        "characterai": "https://neo.character.ai",
        "cohere": "https://api.cohere.com",
        "groq": "https://api.groq.com",
        "qwen": "https://chat.qwen.ai",
        "tongyi": "https://qianwen.biz.aliyun.com",
        "together": "https://api.together.xyz",
        "fireworks": "https://api.fireworks.ai",
        "novita": "https://api.novita.ai",
        "sambanova": "https://api.sambanova.ai",
        "cerebras": "https://api.cerebras.ai",
    }
    for name, expected_url in expected_urls.items():
        cls = _PROVIDERS[name]
        assert cls.default_base_url == expected_url, (
            f"{name}: expected {expected_url!r}, got {cls.default_base_url!r}"
        )
