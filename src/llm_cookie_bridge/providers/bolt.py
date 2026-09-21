from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_jsonl
from .base import BaseProvider


class BoltProvider(BaseProvider):
    """StackBlitz Bolt provider (bolt.new).

    Bolt works anonymously for basic prompts; a StackBlitz session cookie
    unlocks higher limits.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("bolt")

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing project chat.
    * ``model`` – Defaults to ``"claude-sonnet"``.
    """

    provider_name = "bolt"
    default_base_url = "https://bolt.new"

    _CHAT_PATH = "/api/chat"

    DEFAULT_MODEL = "claude-sonnet"

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
            "id": chat_id,
            "messages": [{"role": "user", "content": message}],
            "model": kwargs.get("model", self.DEFAULT_MODEL),
            "files": [],
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for obj in iter_jsonl(response):
                token = ""
                if isinstance(obj, dict):
                    if obj.get("type") == "text-delta":
                        token = obj.get("textDelta") or obj.get("text") or ""
                    else:
                        token = obj.get("text") or obj.get("content") or ""
                elif isinstance(obj, str) and obj.startswith("0:"):
                    token = obj[2:].strip('"')
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
