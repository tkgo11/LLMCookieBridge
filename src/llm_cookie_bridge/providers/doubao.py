from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class DoubaoProvider(BaseProvider):
    """Doubao provider (www.doubao.com) — ByteDance's AI assistant.

    Authentication: full cookie header from a logged-in session at
    https://www.doubao.com (DevTools → Application → Cookies).

    Example::

        bridge = LLMCookieBridge.create(
            "doubao",
            cookie_header=os.environ["DOUBAO_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing conversation.
    * ``web_search`` – Enable search grounding (default ``False``).
    """

    provider_name = "doubao"
    default_base_url = "https://www.doubao.com"

    _CHAT_PATH = "/samantha/chat/completion"

    DEFAULT_MODEL = "default"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Doubao requires session cookies. "
                "Log in at https://www.doubao.com and export the cookie header."
            )
        response = await self.client.get("/")
        if response.status_code in (401, 403):
            raise AuthenticationError(
                f"Doubao session invalid: HTTP {response.status_code}"
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id or "0"

        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": message}],
            "conversation_id": conversation_id,
            "local_conversation_id": random_uuid(),
            "local_message_id": random_uuid(),
            "completion_option": {
                "is_regen": False,
                "with_suggest": True,
                "need_create_conversation": conversation_id == "0",
                "launch_stage": 1,
                "is_replace": False,
                "is_delete": False,
                "message_from": "chat",
                "event_id": "0",
            },
            "evaluate_option": {"web_ab_params": {}},
            "conversation_type": 1,
            "web_search": bool(kwargs.get("web_search")),
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
                event_type = obj.get("event_type") or obj.get("type")
                data = obj.get("message") or obj.get("data") or obj
                token = ""
                conv = conversation_id
                if isinstance(data, dict):
                    token = data.get("content") or data.get("text") or ""
                    conv = data.get("conversation_id") or conv
                if (event_type in ("2001", "2003") or not event_type) and token:
                    latest_text += token
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=token,
                        conversation_id=str(conv),
                        raw=obj,
                    )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=str(conversation_id),
        )
