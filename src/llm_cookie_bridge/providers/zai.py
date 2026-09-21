from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..exceptions import ProviderResponseError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json, openai_delta_text, openai_finish_reason
from .base import BaseProvider


class ZaiProvider(BaseProvider):
    """Z.ai provider (chat.z.ai) — Zhipu's international GLM chat app.

    Z.ai issues anonymous guest JWTs; an account token unlocks higher limits.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("zai")

    Example (authenticated)::

        bridge = LLMCookieBridge.create(
            "zai",
            auth_token=os.environ["ZAI_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"GLM-4.6"``. Others include ``"GLM-4.5"``,
      ``"GLM-4.5-Air"``.
    * ``chat_id`` – Continue an existing chat session.
    * ``web_search`` – Enable web grounding (default ``False``).
    """

    provider_name = "zai"
    default_base_url = "https://chat.z.ai"

    _GUEST_PATH = "/api/v1/auths/guest"
    _NEW_CHAT_PATH = "/api/v2/chats/new"
    _COMPLETIONS_PATH = "/api/v2/chat/completions"

    DEFAULT_MODEL = "GLM-4.6"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        # Anonymous access: request a guest JWT.
        try:
            response = await self.client.post(
                self._GUEST_PATH,
                content=compact_json({"nickname": "guest"}),
                headers={"content-type": "application/json"},
            )
        except httpx.HTTPError:
            response = None
        if response is not None and response.status_code < 400:
            try:
                data = response.json()
                token = (data.get("data") or {}).get("token") or data.get("token")
                if token:
                    self._auth_state["auth_token"] = token
                    self.client.headers["authorization"] = f"Bearer {token}"
                    return
            except (AttributeError, ValueError):
                pass
        # Guest token may be unavailable; continue without it (best effort).
        self._auth_state["auth_token"] = ""

    async def _new_chat(self, model: str) -> str:
        payload = {
            "title": "New Chat",
            "models": [model],
            "chat_mode": "normal",
            "chat_type": "t2t",
            "timestamp": int(time.time() * 1000),
        }
        try:
            response = await self.request(
                "POST",
                self._NEW_CHAT_PATH,
                content=compact_json(payload),
                headers={"content-type": "application/json"},
            )
            data = response.json()
            chat_id = (data.get("data") or {}).get("id") or data.get("id")
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
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": True,
            "chat_type": "t2t",
            "incremental_output": True,
            "feature_config": {"web_search_enabled": bool(kwargs.get("web_search"))},
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            f"{self._COMPLETIONS_PATH}?chat_id={chat_id}",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "source": "web",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                token = openai_delta_text(obj)
                if token:
                    latest_text += token
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=token,
                        conversation_id=chat_id,
                        raw=obj,
                    )
                if openai_finish_reason(obj) in ("stop", "length"):
                    break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
