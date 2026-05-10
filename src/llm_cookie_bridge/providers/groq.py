from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class GroqProvider(BaseProvider):
    """Groq web / API provider (api.groq.com).

    Groq runs open-source models (Llama, Mixtral, Gemma) on custom inference
    hardware for extremely low-latency responses.  The Groq Playground at
    ``console.groq.com`` uses the same OpenAI-compatible REST API.

    Authentication: A Groq API key (starts with ``gsk_``).

    1. Sign in at https://console.groq.com
    2. Go to **Settings → API Keys** and create a new key
    3. Alternatively: Open the Playground → DevTools → Network → any request
       to ``api.groq.com`` → copy ``Authorization: Bearer gsk_...`` header

    Example::

        bridge = LLMCookieBridge.create(
            "groq",
            auth_token=os.environ["GROQ_API_KEY"],
        )

    Provider-specific chat options:

    * ``model`` – Model name; defaults to ``"llama-3.3-70b-versatile"``.
      Others: ``"llama-3.1-8b-instant"``, ``"mixtral-8x7b-32768"``,
      ``"gemma2-9b-it"``, ``"llama3-70b-8192"``.
    * ``temperature`` – Sampling temperature 0.0–2.0 (default 1.0).
    * ``max_tokens`` – Max output tokens (default 1024).
    * ``system`` – System prompt (default ``None``).
    * ``top_p`` – Top-p sampling (default 1.0).
    """

    provider_name = "groq"
    default_base_url = "https://api.groq.com"

    _CHAT_PATH = "/openai/v1/chat/completions"
    _MODELS_PATH = "/openai/v1/models"

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

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
            "Groq requires an API key (starts with 'gsk_'). "
            "Create a free key at https://console.groq.com/settings/api-keys."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        temperature = kwargs.get("temperature", 1.0)
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
