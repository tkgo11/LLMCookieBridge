from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class HailuoProvider(BaseProvider):
    """MiniMax Hailuo AI provider (hailuoai.com / hailuo.ai).

    Authentication: Bearer token from a logged-in session
    (DevTools → Network → any ``/v1/api/chat`` request →
    ``Authorization`` header, or ``localStorage`` token).

    Example::

        bridge = LLMCookieBridge.create(
            "hailuo",
            auth_token=os.environ["HAILUO_TOKEN"],
        )

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing conversation.
    """

    provider_name = "hailuo"
    default_base_url = "https://www.hailuo.ai"

    _CHAT_PATH = "/v1/api/chat/completion"

    DEFAULT_MODEL = "minimax"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"
            self.client.headers["token"] = auth_token

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Hailuo requires an auth_token. "
            "Log in at https://www.hailuo.ai and copy the Bearer token from a "
            "chat request in DevTools."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "chatID": chat_id,
            "msgType": 1,
            "text": message,
            "model": kwargs.get("model", self.DEFAULT_MODEL),
            "chat_type": 1,
            "device_platform": "web",
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
                "referer": f"{self.base_url}/chat",
                "yy": "1",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                if not isinstance(obj, dict):
                    continue
                token = obj.get("content") or obj.get("text") or ""
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
