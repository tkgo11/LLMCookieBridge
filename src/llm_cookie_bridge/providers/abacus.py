from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class AbacusProvider(BaseProvider):
    """Abacus AI ChatLLM provider (apps.abacus.ai / chatllm.abacus.ai).

    Authentication: session cookies or Bearer token from an Abacus account.

    Example::

        bridge = LLMCookieBridge.create(
            "abacus",
            cookie_header=os.environ["ABACUS_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``model`` – e.g. ``"GPT-4o"``, ``"Claude"`` (default).
    * ``chat_id`` – Continue an existing conversation.
    """

    provider_name = "abacus"
    default_base_url = "https://apps.abacus.ai"

    _CHAT_PATH = "/api/chatllm/chat"

    DEFAULT_MODEL = "Claude"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Abacus requires session cookies. "
                "Log in at https://apps.abacus.ai and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.DEFAULT_MODEL),
            "chat_id": chat_id,
            "prompt": message,
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
                "referer": f"{self.base_url}/chatllm",
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
