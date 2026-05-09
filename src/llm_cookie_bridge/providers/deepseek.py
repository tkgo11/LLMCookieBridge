from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..sse import iter_sse
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class DeepSeekProvider(BaseProvider):
    """DeepSeek Chat web provider (chat.deepseek.com).

    Authentication: Extract the Bearer token from localStorage in a logged-in
    browser session at ``https://chat.deepseek.com``.

    In the browser console run::

        JSON.parse(localStorage.getItem("userToken")).value

    Then copy that value as the ``auth_token``.

    Example::

        bridge = LLMCookieBridge.create(
            "deepseek",
            auth_token=os.environ["DEEPSEEK_AUTH_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Model to use: ``"deepseek_chat"`` (default), ``"deepseek_reasoner"``.
    * ``thinking_enabled`` – Enable extended reasoning / thinking (default ``False``).
    * ``search_enabled`` – Enable web search grounding (default ``False``).
    * ``parent_message_id`` – Parent message ID for threading.
    * ``conversation_id`` – Continue an existing chat session.
    """

    provider_name = "deepseek"
    default_base_url = "https://chat.deepseek.com"

    # DeepSeek web API base path
    _API_BASE = "/api/v0"

    DEFAULT_MODEL = "deepseek_chat"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"
            self.client.headers["accept"] = "*/*"
            self.client.headers["content-type"] = "application/json"
            self.client.headers["x-app-version"] = "20241129.1"
            self.client.headers["x-client-locale"] = "en_US"
            self.client.headers["x-client-platform"] = "web"
            self.client.headers["x-client-version"] = "1.0.0-always"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        # DeepSeek requires an auth token set at construction time
        raise AuthenticationError(
            "DeepSeek requires an auth_token. "
            "Run: JSON.parse(localStorage.getItem(\"userToken\")).value "
            "in the browser console at https://chat.deepseek.com"
        )

    async def _create_session(self) -> str:
        """Create a new chat session and return the session ID."""
        response = await self.request(
            "POST",
            f"{self._API_BASE}/chat_session/create",
            content=compact_json({"character_id": None}),
            headers={"content-type": "application/json"},
        )
        data = response.json()
        session_id = (
            (data.get("data") or {})
            .get("biz_data", {})
            .get("id")
        )
        if not session_id:
            raise AuthenticationError(
                "DeepSeek session creation failed; response: "
                + json.dumps(data)[:200]
            )
        return session_id

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id
        if not conversation_id:
            conversation_id = await self._create_session()
            self._conversation_id = conversation_id

        model = kwargs.get("model", self.DEFAULT_MODEL)
        payload: dict[str, Any] = {
            "chat_session_id": conversation_id,
            "parent_message_id": kwargs.get("parent_message_id") or self._message_id,
            "prompt": message,
            "ref_file_ids": [],
            "thinking_enabled": kwargs.get("thinking_enabled", False),
            "search_enabled": kwargs.get("search_enabled", False),
        }
        if model != self.DEFAULT_MODEL:
            payload["model_preference"] = model

        latest_text = ""
        latest_message_id = self._message_id

        async with self.stream_request(
            "POST",
            f"{self._API_BASE}/chat/completion",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        ) as response:
            async for event in iter_sse(response):
                if event.data == "[DONE]":
                    break
                if not event.data:
                    continue
                try:
                    item = json.loads(event.data)
                except json.JSONDecodeError:
                    continue

                choices = item.get("choices") or []
                for choice in choices:
                    delta = choice.get("delta") or {}
                    token = delta.get("content", "")
                    # "thinking" type tokens are internal reasoning; skip for final output
                    delta_type = delta.get("type", "")
                    if delta_type == "thinking":
                        continue
                    if not token:
                        finish = choice.get("finish_reason")
                        if finish == "stop":
                            break
                        continue

                    latest_text += token
                    msg_id = item.get("id") or latest_message_id
                    latest_message_id = msg_id

                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=token,
                        conversation_id=conversation_id,
                        message_id=msg_id,
                        raw=item,
                    )

        self._conversation_id = conversation_id
        self._message_id = latest_message_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
            message_id=latest_message_id,
        )
