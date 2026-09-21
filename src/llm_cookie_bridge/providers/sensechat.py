from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class SenseChatProvider(BaseProvider):
    """SenseTime SenseChat provider (chat.sensetime.com).

    Authentication: Bearer token from a logged-in session at
    https://chat.sensetime.com (SenseTime account required).

    Example::

        bridge = LLMCookieBridge.create(
            "sensechat",
            auth_token=os.environ["SENSECHAT_TOKEN"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing conversation.
    """

    provider_name = "sensechat"
    default_base_url = "https://chat.sensetime.com"

    _CHAT_PATH = "/api/chat/completions"

    DEFAULT_MODEL = "sensechat"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "SenseChat requires an auth_token. "
            "Log in at https://chat.sensetime.com and copy the Bearer token."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.DEFAULT_MODEL),
            "messages": [{"role": "user", "content": message}],
            "conversation_id": conversation_id,
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
