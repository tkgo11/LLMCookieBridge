from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class TongyiProvider(BaseProvider):
    """Alibaba Tongyi Qianwen web provider (www.qianwen.com).

    Tongyi Qianwen (通义千问) was merged into the unified "Qianwen" web app at
    ``https://www.qianwen.com`` — the Chinese counterpart of chat.qwen.ai —
    and shares the same internal API shape.  The old
    ``qianwen.biz.aliyun.com`` dialog API is no longer reachable.

    Authentication: Extract the Bearer token from a logged-in session at
    ``https://www.qianwen.com`` (requires an Alibaba account).

    1. Log in at https://www.qianwen.com
    2. Browser console: ``localStorage.getItem("token")``
       — or copy the ``Authorization: Bearer`` header of any ``completions``
       network request in DevTools.

    Example::

        bridge = LLMCookieBridge.create(
            "tongyi",
            auth_token=os.environ["TONGYI_AUTH_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Qianwen model name (defaults to ``"qwen-plus-latest"``).
    * ``web_search`` – Enable web search grounding (default ``False``).
    * ``thinking`` – Enable chain-of-thought reasoning (default ``False``).
    * ``chat_id`` – Continue an existing chat session UUID.
    """

    provider_name = "tongyi"
    default_base_url = "https://www.qianwen.com"

    _COMPLETIONS_PATH = "/api/v2/chat/completions"
    _NEW_CHAT_PATH = "/api/v2/chats/new"

    DEFAULT_MODEL = "qwen-plus-latest"

    def __init__(
        self,
        *,
        auth_token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"
        self.client.headers["content-type"] = "application/json"
        self.client.headers["origin"] = self.base_url
        self.client.headers["referer"] = f"{self.base_url}/"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Tongyi requires an auth_token. "
            "Log in at https://www.qianwen.com, then copy "
            "localStorage.getItem('token') or the 'Authorization: Bearer ...' "
            "header of any 'completions' request in DevTools."
        )

    async def _new_chat(self, model: str) -> str:
        """Create a chat session and return its chat_id."""
        payload = {
            "title": "New Chat",
            "models": [model],
            "chat_mode": "normal",
            "chat_type": "t2t",
            "timestamp": int(time.time() * 1000),
        }
        response = await self.request(
            "POST",
            self._NEW_CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "source": "web",
            },
        )
        data = response.json()
        chat_id = (data.get("data") or {}).get("id") if isinstance(data, dict) else None
        if not chat_id and isinstance(data, dict):
            chat_id = data.get("id") or data.get("chat_id")
        return chat_id or random_uuid()

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        web_search = kwargs.get("web_search", False)
        thinking = kwargs.get("thinking", False)
        chat_id = kwargs.get("chat_id") or self._conversation_id
        if not chat_id:
            chat_id = await self._new_chat(model)
            self._conversation_id = chat_id

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": message,
                    "chat_type": "t2t",
                    "extra": {},
                    "feature_config": {
                        "thinking_enabled": thinking,
                        "web_search_enabled": web_search,
                    },
                }
            ],
            "stream": True,
            "chat_type": "t2t",
            "chat_mode": "normal",
            "version": "2.1",
            "incremental_output": True,
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
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    token = delta.get("content") or ""
                    if delta.get("role") in ("function", "tool") and not token:
                        continue

                    if token:
                        latest_text += token
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=token,
                            conversation_id=chat_id,
                            raw=data,
                        )

                    if choices[0].get("finish_reason") in ("stop", "length", "content_filter"):
                        break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
