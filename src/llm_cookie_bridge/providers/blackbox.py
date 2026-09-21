from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from .base import BaseProvider


class BlackboxProvider(BaseProvider):
    """Blackbox AI provider (api.blackbox.ai).

    Blackbox pivoted from a cookie-based web chat to an OpenAI-compatible
    inference API.  Requests go to ``https://api.blackbox.ai/chat/completions``
    with a Bearer API key (create one at https://www.blackbox.ai/dashboard).

    Authentication:

    1. Sign in at https://www.blackbox.ai
    2. Create an API key from the dashboard
    3. Pass it as ``auth_token``

    Example::

        bridge = LLMCookieBridge.create(
            "blackbox",
            auth_token=os.environ["BLACKBOX_API_KEY"],
        )

    Provider-specific chat options:

    * ``model`` – Model id; defaults to ``"blackboxai/openai/gpt-4o"``.
      Other examples: ``"blackboxai/anthropic/claude-sonnet-4"``,
      ``"blackboxai/deepseek/deepseek-chat"``,
      ``"blackboxai/meta-llama/llama-3.3-70b-instruct"``.
    * ``messages`` – Full OpenAI-style message history passthrough.
    * ``temperature``, ``max_tokens`` – Forwarded to the API.
    """

    provider_name = "blackbox"
    default_base_url = "https://api.blackbox.ai"

    _CHAT_PATH = "/chat/completions"

    DEFAULT_MODEL = "blackboxai/openai/gpt-4o"

    def __init__(
        self,
        *,
        auth_token: str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        token = auth_token or api_key
        if token:
            self._auth_state["auth_token"] = token
            self.client.headers["authorization"] = f"Bearer {token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Blackbox requires an API key. "
            "Sign in at https://www.blackbox.ai, create a key from the "
            "dashboard, and pass it as auth_token."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        messages = kwargs.get("messages") or [{"role": "user", "content": message}]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]
        if kwargs.get("max_tokens") is not None:
            payload["max_tokens"] = kwargs["max_tokens"]

        latest_text = ""
        response_id: str | None = None

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
                if line == "data: [DONE]":
                    break
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                if data.get("id"):
                    response_id = data["id"]

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
                        message_id=response_id,
                        raw=data,
                    )
                if choices[0].get("finish_reason") in ("stop", "length"):
                    break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            message_id=response_id,
        )
