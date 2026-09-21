from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_jsonl
from .base import BaseProvider


class VeniceProvider(BaseProvider):
    """Venice.ai provider — privacy-focused anonymous AI chat.

    Venice's web client calls ``https://outerface.venice.ai/api/inference/chat``
    which accepts anonymous requests and returns newline-delimited JSON
    ``{"kind": "response", "content": "..."}`` frames.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("venice")

    Provider-specific chat options:

    * ``model`` – Defaults to ``"venice-uncensored"``.
    * ``chat_id`` – Continue an existing conversation.
    """

    provider_name = "venice"
    default_base_url = "https://venice.ai"

    _API_BASE = "https://outerface.venice.ai"
    _CHAT_PATH = "/api/inference/chat"

    DEFAULT_MODEL = "venice-uncensored"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        chat_id = kwargs.get("chat_id") or self._conversation_id

        payload: dict[str, Any] = {
            "requestId": chat_id or "chat",
            "modelId": model,
            "prompt": [{"content": message, "role": "user"}],
            "systemPrompt": "",
            "conversationType": "text",
            "temperature": 0.8,
            "topP": 0.9,
            "webEnabled": bool(kwargs.get("web_search")),
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            f"{self._API_BASE}{self._CHAT_PATH}",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for obj in iter_jsonl(response):
                if not isinstance(obj, dict):
                    continue
                token = ""
                if obj.get("kind") == "response" or obj.get("type") == "response":
                    token = obj.get("content") or obj.get("text") or ""
                elif obj.get("content"):
                    token = obj["content"]
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
