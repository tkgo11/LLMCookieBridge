from __future__ import annotations

from typing import Any, AsyncIterator, Literal

import httpx

from .providers import (
    BlackboxProvider,
    CharacterAIProvider,
    ChatGPTProvider,
    ClaudeProvider,
    CohereProvider,
    CopilotProvider,
    DeepSeekProvider,
    GeminiProvider,
    GroqProvider,
    GrokProvider,
    HuggingFaceProvider,
    MetaAIProvider,
    MistralProvider,
    PerplexityProvider,
    PhindProvider,
    PiProvider,
    PoeProvider,
    QwenProvider,
    TongyiProvider,
    YouProvider,
)
from .providers.base import BaseProvider
from .types import ChatChunk, ChatResponse

ProviderName = Literal[
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
]

_PROVIDERS: dict[str, type[BaseProvider]] = {
    "gemini": GeminiProvider,
    "chatgpt": ChatGPTProvider,
    "claude": ClaudeProvider,
    "perplexity": PerplexityProvider,
    "huggingface": HuggingFaceProvider,
    "grok": GrokProvider,
    "phind": PhindProvider,
    "deepseek": DeepSeekProvider,
    "you": YouProvider,
    "pi": PiProvider,
    "meta": MetaAIProvider,
    "mistral": MistralProvider,
    "copilot": CopilotProvider,
    "poe": PoeProvider,
    "blackbox": BlackboxProvider,
    "characterai": CharacterAIProvider,
    "cohere": CohereProvider,
    "groq": GroqProvider,
    "qwen": QwenProvider,
    "tongyi": TongyiProvider,
}


class LLMCookieBridge:
    def __init__(self, provider: BaseProvider) -> None:
        self.provider = provider

    @classmethod
    def create(
        cls,
        provider: ProviderName,
        *,
        cookies: dict[str, str] | None = None,
        cookie_header: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        refresh_callback: Any = None,
        allow_custom_base_url: bool = False,
        follow_redirects: bool = False,
        **provider_kwargs: Any,
    ) -> "LLMCookieBridge":
        provider_cls = _PROVIDERS[provider]
        instance = provider_cls(
            cookies=cookies,
            cookie_header=cookie_header,
            headers=headers,
            timeout=timeout,
            transport=transport,
            refresh_callback=refresh_callback,
            allow_custom_base_url=allow_custom_base_url,
            follow_redirects=follow_redirects,
            **provider_kwargs,
        )
        return cls(instance)

    async def refresh(self, force: bool = False) -> None:
        await self.provider.refresh(force=force)

    async def chat(self, message: str, **kwargs: Any) -> ChatResponse:
        return await self.provider.chat(message, **kwargs)

    async def stream(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        async for chunk in self.provider.stream_chat(message, **kwargs):
            yield chunk

    async def aclose(self) -> None:
        await self.provider.close()

    async def __aenter__(self) -> "LLMCookieBridge":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
