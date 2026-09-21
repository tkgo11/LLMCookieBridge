from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class AndiProvider(BaseProvider):
    """Andi provider (andisearch.com) — anonymous AI search assistant.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("andi")

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing session.
    """

    provider_name = "andi"
    default_base_url = "https://andisearch.com"

    _CHAT_PATH = "/api/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        with contextlib.suppress(httpx.HTTPError):
            await self.client.get("/")
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "query": message,
            "chat_id": chat_id,
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
