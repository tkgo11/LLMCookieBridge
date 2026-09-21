from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class YuanbaoProvider(BaseProvider):
    """Tencent Yuanbao provider (yuanbao.tencent.com).

    Authentication: full cookie header from a logged-in session at
    https://yuanbao.tencent.com.

    Example::

        bridge = LLMCookieBridge.create(
            "yuanbao",
            cookie_header=os.environ["YUANBAO_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing conversation (chat id).
    * ``model`` – Agent/model id (default ``"hunyuan"``).
    """

    provider_name = "yuanbao"
    default_base_url = "https://yuanbao.tencent.com"

    _CHAT_PATH = "/api/user/agent/conversation"

    DEFAULT_MODEL = "hunyuan"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Yuanbao requires session cookies. "
                "Log in at https://yuanbao.tencent.com and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.DEFAULT_MODEL),
            "prompt": message,
            "plugin": "Adaptive",
            "displayPrompt": message,
            "displayPromptType": 1,
            "options": {"imageIntention": {"needIntentionModel": True}},
            "multimedia": [],
            "agentId": "naQivTmsDa",
            "chatId": conversation_id,
            "supportHint": 0,
            "version": "v2",
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
                "referer": f"{self.base_url}/chat/",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                if not isinstance(obj, dict):
                    continue
                token = obj.get("content") or obj.get("msg") or ""
                if isinstance(obj.get("data"), dict):
                    token = token or obj["data"].get("content", "")
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
