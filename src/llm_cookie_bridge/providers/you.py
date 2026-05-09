from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from .base import BaseProvider


class YouProvider(BaseProvider):
    """You.com YouChat web provider.

    Authentication: Log into https://you.com, then export cookies from
    your browser session.  Key cookies include ``afUserId`` and ``you_subscription``
    (for access to non-default models).

    Anonymous (no login) access works for basic queries with the default model.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("you")

    Example (authenticated)::

        bridge = LLMCookieBridge.create(
            "you",
            cookie_header=os.environ["YOU_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``model`` – Model alias; e.g. ``"gpt-4o"``, ``"claude-3.5-sonnet"``,
      ``"llama-3.3-70b"``, etc.  Defaults to ``"default"`` (You's own model).
    * ``chat_mode`` – ``"default"`` | ``"custom"`` | ``"create"`` | ``"agent"``.
      Inferred automatically from the model when not set.
    * ``chat_id`` – Re-use a previous chat UUID.
    """

    provider_name = "you"
    default_base_url = "https://you.com"

    # Model → internal alias mapping
    MODEL_MAP: dict[str, str] = {
        "gpt-4o": "gpt_4o",
        "gpt-4o-mini": "gpt_4o_mini",
        "gpt-4-turbo": "gpt_4_turbo",
        "grok-2": "grok_2",
        "claude-3.5-sonnet": "claude_3_5_sonnet",
        "claude-3.5-haiku": "claude_3_5_haiku",
        "claude-3-opus": "claude_3_opus",
        "claude-3-sonnet": "claude_3_sonnet",
        "claude-3-haiku": "claude_3_haiku",
        "llama-3.3-70b": "llama3_3_70b",
        "llama-3.1-70b": "llama3_1_70b",
        "gemini-1.5-flash": "gemini_1_5_flash",
        "gemini-1.5-pro": "gemini_1_5_pro",
        "command-r": "command_r",
        "command-r-plus": "command_r_plus",
    }

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        # You.com works without strict auth; just verify connectivity.
        response = await self.client.get("/")
        if response.status_code >= 400:
            raise AuthenticationError(
                f"You.com session bootstrap failed: HTTP {response.status_code}"
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", "")
        chat_mode = kwargs.get("chat_mode", "")

        if not chat_mode:
            if model in self.MODEL_MAP or model:
                chat_mode = "custom"
            else:
                chat_mode = "default"

        internal_model = self.MODEL_MAP.get(model, model)

        params: dict[str, Any] = {
            "q": message,
            "domain": "youchat",
            "selectedChatMode": chat_mode,
            "conversationTurnId": str(uuid.uuid4()),
            "chatId": kwargs.get("chat_id") or str(uuid.uuid4()),
        }

        if chat_mode == "custom" and internal_model:
            params["selectedAiModel"] = internal_model

        latest_text = ""

        async with self.stream_request(
            "GET",
            "/api/streamingSearch",
            params=params,
            headers={
                "accept": "text/event-stream",
                "referer": f"{self.base_url}/api/streamingSearch",
            },
        ) as response:
            event = ""
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event = line[7:].strip()
                elif line.startswith("data: "):
                    raw_data = line[6:]
                    if event in ("youChatToken", "youChatUpdate"):
                        try:
                            payload = json.loads(raw_data)
                        except json.JSONDecodeError:
                            continue

                        token: str = ""
                        if event == "youChatToken":
                            token = payload.get("youChatToken", "")
                        elif event == "youChatUpdate":
                            token = payload.get("t", "")

                        if not token:
                            continue

                        # Skip quota-exceeded messages
                        if "hit your free quota" in token:
                            continue

                        latest_text += token
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=token,
                            raw=payload,
                        )
                    elif event == "error":
                        raise AuthenticationError(f"You.com error: {raw_data}")

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
        )
