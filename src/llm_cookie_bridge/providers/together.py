from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class TogetherProvider(BaseProvider):
    """Together AI provider (api.together.xyz / api.together.ai).

    Together AI offers a large catalogue of open-source models (Llama,
    Mistral, Qwen, DeepSeek, Code Llama, and many more) through an
    OpenAI-compatible REST API.

    Authentication: A Together AI API key.

    1. Sign up or log in at https://api.together.ai
    2. Go to **Settings → API Keys** and create/copy a key.

    Example::

        bridge = LLMCookieBridge.create(
            "together",
            auth_token=os.environ["TOGETHER_API_KEY"],
        )

    Provider-specific chat options:

    * ``model`` – Model path, defaults to ``"meta-llama/Llama-3.3-70B-Instruct-Turbo"``.
      See https://api.together.ai/models for the full list.
    * ``system`` – System prompt.
    * ``temperature`` – Sampling temperature (default 0.7).
    * ``max_tokens`` – Max output tokens (default 1024).
    * ``top_p`` – Top-p sampling (default 0.7).
    * ``top_k`` – Top-k sampling (default 50).
    """

    provider_name = "together"
    default_base_url = "https://api.together.xyz"

    _CHAT_PATH = "/v1/chat/completions"

    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

    def __init__(
        self,
        *,
        auth_token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"
            self.client.headers["content-type"] = "application/json"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Together AI requires an API key. "
            "Create a free key at https://api.together.ai/settings/api-keys."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 1024)
        top_p = kwargs.get("top_p", 0.7)
        top_k = kwargs.get("top_k", 50)
        system = kwargs.get("system")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
        }

        request_id = random_uuid()
        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    token = delta.get("content") or ""

                    if token:
                        latest_text += token
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=token,
                            conversation_id=data.get("id") or request_id,
                            raw=data,
                        )

                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason in ("stop", "eos", "length", "content_filter"):
                        break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=request_id,
        )
