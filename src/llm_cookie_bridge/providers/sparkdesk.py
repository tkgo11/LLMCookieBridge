from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class SparkDeskProvider(BaseProvider):
    """iFlytek SparkDesk provider (xinghuo.xfyun.cn).

    Authentication: full cookie header from a logged-in session at
    https://xinghuo.xfyun.cn (requires an iFlytek account).

    Example::

        bridge = LLMCookieBridge.create(
            "sparkdesk",
            cookie_header=os.environ["SPARKDESK_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing chat.
    """

    provider_name = "sparkdesk"
    default_base_url = "https://xinghuo.xfyun.cn"

    _CHAT_PATH = "/u/chat_message/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "SparkDesk requires session cookies. "
                "Log in at https://xinghuo.xfyun.cn and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or "0"
        fd = random_uuid().replace("-", "")

        payload: dict[str, Any] = {
            "fd": fd,
            "chatId": chat_id,
            "text": message,
            "clientType": 1,
            "GtTokens": "",
            "isBot": False,
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
                "referer": f"{self.base_url}/desk",
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
                    conversation_id=str(chat_id),
                    raw=obj,
                )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=str(chat_id),
        )
