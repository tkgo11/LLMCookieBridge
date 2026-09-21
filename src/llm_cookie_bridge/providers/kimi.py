from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..exceptions import AuthenticationError, ProviderResponseError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class KimiProvider(BaseProvider):
    """Kimi provider (kimi.com) — Moonshot AI's web chat.

    Authentication: Extract the Bearer token from a logged-in session.

    1. Log in at https://www.kimi.com
    2. Browser console: ``localStorage.getItem("access_token")``
       — or copy the ``Authorization: Bearer`` header from any
       ``/api/chat`` request in DevTools.

    Example::

        bridge = LLMCookieBridge.create(
            "kimi",
            auth_token=os.environ["KIMI_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"kimi"``. Others include ``"kimi-k2"``.
    * ``chat_id`` – Continue an existing Kimi conversation.
    * ``web_search`` – Enable search grounding (default ``False``).
    """

    provider_name = "kimi"
    default_base_url = "https://www.kimi.com"

    _NEW_CHAT_PATH = "/api/chat"
    _COMPLETION_TPL = "/api/chat/{chat_id}/completion/stream"

    DEFAULT_MODEL = "kimi"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Kimi requires an auth_token. "
            "Log in at https://www.kimi.com, then copy "
            "localStorage.getItem('access_token') or the 'Authorization: "
            "Bearer ...' header of any /api/chat request."
        )

    async def _new_chat(self, model: str) -> str:
        payload = {
            "name": "New chat",
            "born_from": "home",
            "kimiplus_id": model if model != "kimi" else "kimi",
            "is_example": False,
            "status": "normal",
        }
        try:
            response = await self.request(
                "POST",
                self._NEW_CHAT_PATH,
                content=compact_json(payload),
                headers={"content-type": "application/json"},
            )
            data = response.json()
            chat_id = data.get("id") or (data.get("data") or {}).get("id")
        except (httpx.HTTPError, ProviderResponseError, ValueError):
            chat_id = None
        return chat_id or random_uuid()

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        chat_id = kwargs.get("chat_id") or self._conversation_id
        if not chat_id:
            chat_id = await self._new_chat(model)
            self._conversation_id = chat_id

        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": message}],
            "refs": [],
            "use_search": bool(kwargs.get("web_search")),
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._COMPLETION_TPL.format(chat_id=chat_id),
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                # Kimi streams {"event": "cmpl", "text": "..."} objects
                token = ""
                if isinstance(obj, dict):
                    token = obj.get("text") or obj.get("content") or ""
                    if not token and obj.get("event") in ("cmpl", "message"):
                        token = (obj.get("data") or {}).get("text", "")
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

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
