from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class CozeProvider(BaseProvider):
    """Coze provider (coze.com) — ByteDance's bot platform.

    Authentication: session cookies from https://www.coze.com.

    Example::

        bridge = LLMCookieBridge.create(
            "coze",
            cookie_header=os.environ["COZE_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``bot_id`` – The Coze bot to chat with.
    * ``conversation_id`` – Continue an existing conversation.
    """

    provider_name = "coze"
    default_base_url = "https://www.coze.com"

    _CHAT_PATH = "/api/conversation/chat"

    DEFAULT_BOT = "7344444444444444444"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Coze requires session cookies. "
                "Log in at https://www.coze.com and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        bot_id = kwargs.get("bot_id") or self._auth_state.get("bot_id") or self.DEFAULT_BOT
        conversation_id = kwargs.get("conversation_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "bot_id": bot_id,
            "conversation_id": conversation_id,
            "query": message,
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
                if not isinstance(obj, dict):
                    continue
                token = obj.get("content") or obj.get("text") or ""
                msg = obj.get("message") or {}
                if not token and isinstance(msg, dict):
                    token = msg.get("content") or ""
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    conversation_id=str(conversation_id),
                    raw=obj,
                )

        self._conversation_id = conversation_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=str(conversation_id),
        )
