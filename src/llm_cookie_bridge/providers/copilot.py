from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..sse import iter_sse
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class CopilotProvider(BaseProvider):
    """Microsoft Copilot web provider (copilot.microsoft.com).

    Authentication: Log into https://copilot.microsoft.com, then export
    the full cookie header string (including ``_U``, ``MUID``, and any
    Microsoft auth cookies).

    For anonymous (unauthenticated) use, you still need a guest session.
    Pass ``cookie_header`` for the best results.

    Example::

        bridge = LLMCookieBridge.create(
            "copilot",
            cookie_header=os.environ["COPILOT_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue an existing Copilot conversation.
    * ``tone`` – ``"Balanced"`` (default), ``"Creative"``, ``"Precise"``.
    * ``locale`` – Language locale tag (default ``"en-US"``).
    """

    provider_name = "copilot"
    default_base_url = "https://copilot.microsoft.com"

    _API_ENDPOINT = "/c/api/chat"

    DEFAULT_TONE = "Balanced"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        response = await self.client.get(
            "/",
            headers={"accept": "text/html,application/xhtml+xml"},
        )
        if response.status_code >= 400:
            raise AuthenticationError(
                f"Copilot session bootstrap failed: HTTP {response.status_code}"
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id
        tone = kwargs.get("tone", self.DEFAULT_TONE)
        locale = kwargs.get("locale", "en-US")

        payload: dict[str, Any] = {
            "prompt": message,
            "conversationId": conversation_id or random_uuid(),
            "tone": tone,
            "locale": locale,
        }
        if not conversation_id:
            payload["isStartOfSession"] = True

        latest_text = ""
        new_conversation_id = conversation_id

        async with self.stream_request(
            "POST",
            self._API_ENDPOINT,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for event in iter_sse(response):
                if not event.data or event.data == "[DONE]":
                    break
                try:
                    obj = json.loads(event.data)
                except json.JSONDecodeError:
                    continue

                event_type = obj.get("type") or obj.get("event")

                # Handle delta-style streaming
                choices = obj.get("choices") or []
                for choice in choices:
                    delta_obj = choice.get("delta") or {}
                    delta = delta_obj.get("content", "")
                    if delta:
                        latest_text += delta
                        new_conversation_id = (
                            obj.get("conversationId") or new_conversation_id
                        )
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=delta,
                            conversation_id=new_conversation_id,
                            raw=obj,
                        )

                # Some Copilot versions stream text directly
                if not choices:
                    text = obj.get("text") or obj.get("body") or ""
                    if text:
                        delta = compute_delta(text, latest_text)
                        latest_text = text
                        new_conversation_id = (
                            obj.get("conversationId") or new_conversation_id
                        )
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=delta,
                            conversation_id=new_conversation_id,
                            raw=obj,
                        )

        self._conversation_id = new_conversation_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=new_conversation_id,
        )
