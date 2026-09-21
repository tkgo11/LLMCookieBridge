from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class BaichuanProvider(BaseProvider):
    """Baichuan AI provider (www.baichuan-ai.com).

    Authentication: session cookies from a Baichuan account at
    https://www.baichuan-ai.com.

    Example::

        bridge = LLMCookieBridge.create(
            "baichuan",
            cookie_header=os.environ["BAICHUAN_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing conversation.
    """

    provider_name = "baichuan"
    default_base_url = "https://www.baichuan-ai.com"

    _CHAT_PATH = "/api/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Baichuan requires session cookies. "
                "Log in at https://www.baichuan-ai.com and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "conversation_id": conversation_id,
            "query": message,
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
