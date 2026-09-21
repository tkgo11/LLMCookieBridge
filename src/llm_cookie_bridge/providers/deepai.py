from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class DeepAIProvider(BaseProvider):
    """DeepAI provider (deepai.org) — anonymous AI chat.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("deepai")

    Example (with API key for higher limits)::

        bridge = LLMCookieBridge.create("deepai", auth_token=os.environ["DEEPAI_KEY"])

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing session.
    """

    provider_name = "deepai"
    default_base_url = "https://deepai.org"

    _CHAT_PATH = "/hacking_is_a_serious_crime"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["api-key"] = auth_token

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        with contextlib.suppress(httpx.HTTPError):
            await self.client.get("/chat")
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id

        payload: dict[str, Any] = {
            "chat_style": "chat",
            "chatHistory": compact_json([{"role": "user", "content": message}]),
        }
        if chat_id:
            payload["chat_uuid"] = chat_id

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "origin": self.base_url,
                "referer": f"{self.base_url}/chat",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                token = openai_delta_text(obj)
                if not token and isinstance(obj, dict):
                    token = obj.get("message") or obj.get("text") or obj.get("content") or ""
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    conversation_id=chat_id,
                    raw=obj,
                )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
