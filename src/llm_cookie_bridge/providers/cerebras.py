from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class CerebrasProvider(BaseProvider):
    """Cerebras Inference provider (api.cerebras.ai).

    Cerebras offers ultra-fast token generation on wafer-scale chip clusters.
    The API is OpenAI-compatible.

    Authentication: A Cerebras API key.

    1. Sign up at https://cloud.cerebras.ai
    2. Go to **API Keys** in your dashboard.

    Example::

        bridge = LLMCookieBridge.create(
            "cerebras",
            auth_token=os.environ["CEREBRAS_API_KEY"],
        )

    Provider-specific chat options:

    * ``model`` – Model name, defaults to ``"llama3.1-70b"``.
      Others: ``"llama3.1-8b"``, ``"llama-4-scout-17b-16e-instruct"``.
    * ``system`` – System prompt.
    * ``temperature`` – Sampling temperature (default 0.7).
    * ``max_tokens`` – Max output tokens (default 1024).
    """

    provider_name = "cerebras"
    default_base_url = "https://api.cerebras.ai"

    _CHAT_PATH = "/v1/chat/completions"

    DEFAULT_MODEL = "llama3.1-70b"

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
            "Cerebras requires an API key. "
            "Sign up at https://cloud.cerebras.ai and create an API key."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 1024)
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
                    if finish_reason in ("stop", "length"):
                        break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=request_id,
        )
