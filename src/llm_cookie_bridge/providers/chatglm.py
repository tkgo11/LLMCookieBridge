from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json
from .base import BaseProvider


class ChatGLMProvider(BaseProvider):
    """Zhipu ChatGLM / Qingyan provider (chatglm.cn).

    Authentication: the ``chatglm_token`` / session Bearer used by
    chatglm.cn (DevTools → Network → any ``backendchat`` request →
    ``Authorization`` header, or ``localStorage``).

    Example::

        bridge = LLMCookieBridge.create(
            "chatglm",
            auth_token=os.environ["CHATGLM_TOKEN"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing conversation.
    * ``web_search`` – Enable search grounding (default ``False``).
    """

    provider_name = "chatglm"
    default_base_url = "https://chatglm.cn"

    _CHAT_PATH = "/chatglm/backendchat/assistant/stream"

    DEFAULT_MODEL = "glm-4"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "ChatGLM requires an auth_token. "
            "Log in at https://chatglm.cn and copy the Bearer token from a "
            "backendchat request in DevTools."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "assistant_id": "65a232a0ffcf90ddf8f4d37f",
            "conversation_id": conversation_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": message}],
                }
            ],
            "meta_data": {
                "is_test": False,
                "input_question_type": "xxxx",
                "channel": "",
                "draft_id": "",
                "chat_mode": "zero",
            },
        }
        if kwargs.get("web_search"):
            payload["meta_data"]["if_use_search"] = True

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
                "x-request-id": random_uuid(),
                "x-app-platform": "pc",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                if not isinstance(obj, dict):
                    continue
                token = ""
                parts = obj.get("parts") or []
                if parts and isinstance(parts[0], dict):
                    content = parts[0].get("content") or []
                    if content and isinstance(content[0], dict):
                        token = content[0].get("text") or ""
                token = token or obj.get("text") or obj.get("content") or ""
                status = obj.get("status")
                if token and status != "init":
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
