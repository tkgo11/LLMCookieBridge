from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class LMArenaProvider(BaseProvider):
    """LMArena provider (lmarena.ai) — LMSYS Chatbot Arena web chat.

    The arena's side-by-side chat works anonymously; the site issues session
    cookies on first load which are then used for the streaming chat API.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("lmarena")

    Provider-specific chat options:

    * ``model`` – Arena model slug (e.g. ``"gpt-4o"``, ``"claude-3-5-sonnet"``).
    * ``chat_id`` – Continue an existing session.
    """

    provider_name = "lmarena"
    default_base_url = "https://lmarena.ai"

    _CHAT_PATH = "/api/v0/arena/chat"

    DEFAULT_MODEL = "default"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        # Prime the session cookies by loading the site root.
        response = await self.client.get("/")
        if response.status_code < 400:
            self._auth_state["primed"] = True
            return
        self._auth_state["primed"] = True  # best-effort; arena is anonymous

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "chat_id": chat_id,
            "stream": True,
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
                token = openai_delta_text(obj)
                if not token and isinstance(obj, dict):
                    token = obj.get("text") or obj.get("content") or ""
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
