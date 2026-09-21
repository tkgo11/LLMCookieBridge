from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class AI360Provider(BaseProvider):
    """360 Zhinao provider (bot.n.cn) — 360's AI assistant.

    Authentication: session cookies from https://bot.n.cn.

    Example::

        bridge = LLMCookieBridge.create(
            "ai360",
            cookie_header=os.environ["AI360_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing conversation.
    """

    provider_name = "ai360"
    default_base_url = "https://bot.n.cn"

    _CHAT_PATH = "/api/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "AI360 requires session cookies. "
                "Log in at https://bot.n.cn and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "conversation_id": conversation_id,
            "prompt": message,
            "messages": [{"role": "user", "content": message}],
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
                    conversation_id=conversation_id,
                    raw=obj,
                )

        self._conversation_id = conversation_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
        )
