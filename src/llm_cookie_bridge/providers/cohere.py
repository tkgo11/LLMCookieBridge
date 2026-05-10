from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class CohereProvider(BaseProvider):
    """Cohere Coral web provider (chat.cohere.com / api.cohere.com).

    Cohere's Coral web interface calls the same public API at
    ``api.cohere.com/v2/chat``.  You can authenticate either with:

    * A **session JWT** extracted from the Coral browser session (short-lived,
      obtained after logging in at https://chat.cohere.com), OR
    * A **Cohere API key** from https://dashboard.cohere.com/api-keys (stable).

    In both cases the token is passed as ``Authorization: Bearer <token>``.

    To extract the session token from browser:

    1. Log in to https://chat.cohere.com
    2. Open DevTools → Network tab → filter by Fetch/XHR
    3. Send a message in the chat
    4. Find the POST to ``/v2/chat`` on api.cohere.com
    5. Copy the ``Authorization: Bearer <token>`` header value

    Example::

        bridge = LLMCookieBridge.create(
            "cohere",
            auth_token=os.environ["COHERE_API_KEY"],  # API key or session JWT
        )

    Provider-specific chat options:

    * ``model`` – Model name, defaults to ``"command-r-plus"``.
      Others: ``"command-r"``, ``"command-a-03-2025"``.
    * ``preamble`` – System/instruction prompt (default empty).
    * ``temperature`` – Sampling temperature (default 0.7).
    * ``max_tokens`` – Max output tokens (default 4096).
    * ``web_search`` – Enable web connectors (default ``False``).
    * ``chat_history`` – List of prior ``{"role": ..., "content": ...}`` turns.
    """

    provider_name = "cohere"
    default_base_url = "https://api.cohere.com"

    _CHAT_PATH = "/v2/chat"

    DEFAULT_MODEL = "command-r-plus"

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
            self.client.headers["accept"] = "text/event-stream"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Cohere requires an auth_token. "
            "Get a free API key at https://dashboard.cohere.com/api-keys, "
            "or extract a session JWT from https://chat.cohere.com via "
            "DevTools → Network → any /v2/chat request → Authorization header."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        preamble = kwargs.get("preamble", "")
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)
        web_search = kwargs.get("web_search", False)
        chat_history: list[dict[str, str]] = list(kwargs.get("chat_history") or [])

        # Build messages: history + current user turn
        messages = list(chat_history)
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if preamble:
            payload["preamble"] = preamble

        if web_search:
            payload["connectors"] = [{"id": "web-search"}]

        conversation_id = self._conversation_id or random_uuid()
        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    event_type = data.get("type", "")

                    if event_type == "content-delta":
                        delta_obj = data.get("delta") or {}
                        token = delta_obj.get("text") or delta_obj.get("message", {}).get("content", {}).get("text", "")
                        if token:
                            latest_text += token
                            yield ChatChunk(
                                provider=self.provider_name,
                                text=latest_text,
                                delta=token,
                                conversation_id=conversation_id,
                                raw=data,
                            )

                    elif event_type == "message-end":
                        finish_reason = data.get("finish_reason", "")
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta="",
                            done=True,
                            conversation_id=conversation_id,
                            metadata={"finish_reason": finish_reason},
                        )
                        return

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
        )
