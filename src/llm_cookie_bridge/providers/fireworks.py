from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class FireworksProvider(BaseProvider):
    """Fireworks AI provider (api.fireworks.ai).

    Fireworks AI offers fast inference for open-source models (Llama,
    DeepSeek, Qwen, Mistral, Phi, and more) through an OpenAI-compatible API.

    Authentication: A Fireworks AI API key.

    1. Sign up or log in at https://fireworks.ai
    2. Go to **API Keys** and create a key.

    Example::

        bridge = LLMCookieBridge.create(
            "fireworks",
            auth_token=os.environ["FIREWORKS_API_KEY"],
        )

    Provider-specific chat options:

    * ``model`` – Model path, defaults to
      ``"accounts/fireworks/models/llama-v3p3-70b-instruct"``.
      See https://fireworks.ai/models for the full catalogue.
    * ``system`` – System prompt.
    * ``temperature`` – Sampling temperature (default 0.6).
    * ``max_tokens`` – Max output tokens (default 1024).
    * ``top_p`` – Top-p sampling (default 1.0).
    """

    provider_name = "fireworks"
    default_base_url = "https://api.fireworks.ai"

    _CHAT_PATH = "/inference/v1/chat/completions"

    DEFAULT_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"

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
            self.client.headers["accept"] = "application/json"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Fireworks AI requires an API key. "
            "Create a free key at https://fireworks.ai/account/api-keys."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        temperature = kwargs.get("temperature", 0.6)
        max_tokens = kwargs.get("max_tokens", 1024)
        top_p = kwargs.get("top_p", 1.0)
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
                    if finish_reason in ("stop", "length", "content_filter"):
                        break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=request_id,
        )
