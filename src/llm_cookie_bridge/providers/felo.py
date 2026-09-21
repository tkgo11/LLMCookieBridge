from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class FeloProvider(BaseProvider):
    """Felo AI provider (felo.ai) — multilingual AI search chat.

    Authentication: session cookies from https://felo.ai (anonymous queries
    work for basic searches).

    Example::

        bridge = LLMCookieBridge.create("felo")

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing thread.
    """

    provider_name = "felo"
    default_base_url = "https://felo.ai"

    _CHAT_PATH = "/api/search/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        try:
            response = await self.client.get("/")
        except httpx.HTTPError:
            response = None
        if response is not None and response.status_code >= 400:
            raise AuthenticationError(
                f"Felo session bootstrap failed: HTTP {response.status_code}"
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "query": message,
            "chat_id": chat_id,
            "lang": kwargs.get("lang", "en"),
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                if not isinstance(obj, dict):
                    continue
                token = obj.get("text") or obj.get("content") or obj.get("answer") or ""
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

        self._conversation_id = chat_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
