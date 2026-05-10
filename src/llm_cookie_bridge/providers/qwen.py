from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class QwenProvider(BaseProvider):
    """Alibaba Qwen Chat web provider (chat.qwen.ai).

    Authentication: Extract the Bearer token from the browser session at
    ``https://chat.qwen.ai``.

    1. Log in to https://chat.qwen.ai
    2. Open DevTools → Network tab → filter by ``Fetch/XHR``
    3. Send a message and find the ``completions`` request
    4. In **Request Headers**, copy the value after ``Authorization: Bearer ``
    5. Optionally also copy the full ``Cookie`` header for better stability

    Alternative method (Console):
    ``localStorage.getItem("token")`` → copy the token without quotes

    Example::

        bridge = LLMCookieBridge.create(
            "qwen",
            auth_token=os.environ["QWEN_AUTH_TOKEN"],
            # optional for better stability:
            cookie_header=os.environ.get("QWEN_COOKIE", ""),
        )

    Provider-specific chat options:

    * ``model`` – Qwen model name. Defaults to ``"qwen-plus-latest"``.
      Others: ``"qwen-max-latest"``, ``"qwen-turbo-latest"``, ``"qwq-32b"``,
      ``"qwen2.5-coder-32b-instruct"``, ``"qwen2.5-72b-instruct"``.
    * ``web_search`` – Enable web search grounding (default ``False``).
    * ``thinking`` – Enable chain-of-thought reasoning (default ``False``).
    * ``chat_id`` – Continue an existing chat session UUID.
    """

    provider_name = "qwen"
    default_base_url = "https://chat.qwen.ai"

    _COMPLETIONS_PATH = "/api/chat/completions"
    _NEW_CHAT_PATH = "/api/v1/chats/new"

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
            self.client.headers["origin"] = "https://chat.qwen.ai"
            self.client.headers["referer"] = "https://chat.qwen.ai/"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Qwen requires an auth_token. "
            "Log in at https://chat.qwen.ai, open DevTools → Network, "
            "find any 'completions' request and copy the "
            "'Authorization: Bearer ...' header value. "
            "Or use: localStorage.getItem('token') in the browser console."
        )

    def _build_message(
        self, role: str, content: str, web_search: bool = False, thinking: bool = False
    ) -> dict[str, Any]:
        return {
            "role": role,
            "content": content,
            "chat_type": "t2t",
            "extra": {},
            "feature_config": {
                "thinking_enabled": thinking,
                "web_search_enabled": web_search,
            },
        }

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        web_search = kwargs.get("web_search", False)
        thinking = kwargs.get("thinking", False)
        chat_id = kwargs.get("chat_id") or self._conversation_id

        messages = [self._build_message("user", message, web_search, thinking)]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "chat_type": "t2t",
            "id": chat_id or random_uuid(),
            "incremental_output": True,
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._COMPLETIONS_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    raw = line[6:]
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    token = delta.get("content") or ""

                    # Skip thinking tokens (they are in separate key or role)
                    if delta.get("role") in ("function", "tool") and not token:
                        continue

                    if token:
                        latest_text += token
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=token,
                            conversation_id=payload["id"],
                            raw=data,
                        )

                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason in ("stop", "length", "content_filter"):
                        break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=payload["id"],
        )
