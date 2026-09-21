from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class KagiProvider(BaseProvider):
    """Kagi Assistant provider (kagi.com).

    Authentication: session cookie from a Kagi account (Assistant requires a
    paid Kagi plan).

    Example::

        bridge = LLMCookieBridge.create(
            "kagi",
            cookie_header=os.environ["KAGI_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing assistant thread.
    * ``model`` – Defaults to ``"kagi"`` (auto model pick).
    """

    provider_name = "kagi"
    default_base_url = "https://kagi.com"

    _CHAT_PATH = "/assistant/chat"

    DEFAULT_MODEL = "kagi"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Kagi requires session cookies (paid account). "
                "Log in at https://kagi.com and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "prompt": message,
            "chat_id": chat_id,
            "model": kwargs.get("model", self.DEFAULT_MODEL),
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
                "referer": f"{self.base_url}/assistant",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                if not isinstance(obj, dict):
                    continue
                token = obj.get("text") or obj.get("content") or obj.get("token") or ""
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
