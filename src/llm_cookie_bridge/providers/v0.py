from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_jsonl
from .base import BaseProvider


class V0Provider(BaseProvider):
    """Vercel v0 provider (v0.dev).

    Authentication: session cookies from a Vercel account at https://v0.dev.

    Example::

        bridge = LLMCookieBridge.create(
            "v0",
            cookie_header=os.environ["VERCEL_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``chat_id`` – Continue an existing v0 chat.
    * ``model`` – Defaults to ``"v0-1.0-md"``.
    """

    provider_name = "v0"
    default_base_url = "https://v0.dev"

    _CHAT_PATH = "/api/chat"

    DEFAULT_MODEL = "v0-1.0-md"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "v0 requires Vercel session cookies. "
                "Log in at https://v0.dev and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "id": chat_id,
            "messages": [{"role": "user", "content": message}],
            "model": kwargs.get("model", self.DEFAULT_MODEL),
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for obj in iter_jsonl(response):
                token = ""
                if isinstance(obj, dict):
                    if obj.get("type") == "text-delta":
                        token = obj.get("textDelta") or obj.get("text") or ""
                    elif not token:
                        token = obj.get("text") or obj.get("content") or ""
                elif isinstance(obj, str) and obj.startswith("0:"):
                    token = obj[2:].strip('"')
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
