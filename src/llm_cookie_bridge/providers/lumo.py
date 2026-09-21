from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class LumoProvider(BaseProvider):
    """Proton Lumo provider (lumo.proton.me).

    Authentication: session cookies from a Proton account at
    https://lumo.proton.me.

    Example::

        bridge = LLMCookieBridge.create(
            "lumo",
            cookie_header=os.environ["PROTON_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing conversation.
    """

    provider_name = "lumo"
    default_base_url = "https://lumo.proton.me"

    _CHAT_PATH = "/api/ai/v1/chat/completions"

    DEFAULT_MODEL = "lumo"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Lumo requires Proton session cookies. "
                "Log in at https://lumo.proton.me and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.DEFAULT_MODEL),
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
