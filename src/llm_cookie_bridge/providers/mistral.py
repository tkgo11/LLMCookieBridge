from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..sse import iter_sse
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class MistralProvider(BaseProvider):
    """Mistral Le Chat web provider (chat.mistral.ai).

    Authentication: Log into https://chat.mistral.ai, then export the
    ``mistral-chat-session`` cookie (or the full cookie header string).

    Example::

        bridge = LLMCookieBridge.create(
            "mistral",
            cookie_header=os.environ["MISTRAL_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``model`` – Mistral model ID, e.g. ``"mistral-large-latest"`` (default),
      ``"mistral-small-latest"``, ``"codestral-latest"``.
    * ``conversation_id`` – Continue an existing conversation UUID.
    * ``system_prompt`` – System prompt for new conversations.
    """

    provider_name = "mistral"
    default_base_url = "https://chat.mistral.ai"

    DEFAULT_MODEL = "mistral-large-latest"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        response = await self.client.get(
            "/",
            headers={"accept": "text/html,application/xhtml+xml"},
        )
        if response.status_code >= 400:
            raise AuthenticationError(
                f"Mistral Le Chat session bootstrap failed: HTTP {response.status_code}"
            )
        self._auth_state["primed"] = True

    async def _create_conversation(
        self,
        model: str,
        system_prompt: str = "",
    ) -> str:
        """Create a new Mistral Le Chat conversation."""
        payload: dict[str, Any] = {"model": model}
        if system_prompt:
            payload["systemPrompt"] = system_prompt
        response = await self.request(
            "POST",
            "/api/chat/new",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "origin": self.base_url,
                "referer": f"{self.base_url}/chat",
            },
        )
        data = response.json()
        cid = data.get("id") or data.get("conversationId") or data.get("conversation_id")
        if not cid:
            # Fallback: generate a UUID – some endpoints echo it back
            cid = random_uuid()
        return cid

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        system_prompt = kwargs.get("system_prompt", "")
        conversation_id = kwargs.get("conversation_id") or self._conversation_id

        if not conversation_id:
            conversation_id = await self._create_conversation(model, system_prompt)
            self._conversation_id = conversation_id

        payload: dict[str, Any] = {
            "conversationId": conversation_id,
            "message": message,
            "model": model,
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            "/api/chat",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "origin": self.base_url,
                "referer": f"{self.base_url}/chat/{conversation_id}",
            },
        ) as response:
            async for event in iter_sse(response):
                if event.data in ("[DONE]", ""):
                    break
                try:
                    obj = json.loads(event.data)
                except json.JSONDecodeError:
                    continue

                # Le Chat uses a delta-style SSE format
                choices = obj.get("choices") or []
                for choice in choices:
                    delta = (choice.get("delta") or {}).get("content", "")
                    if delta:
                        latest_text += delta
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=delta,
                            conversation_id=conversation_id,
                            raw=obj,
                        )
                    if choice.get("finish_reason") == "stop":
                        break

                # Some versions send a "content" key directly
                if not choices:
                    content = obj.get("content") or obj.get("text") or ""
                    if content:
                        delta = compute_delta(content, latest_text)
                        latest_text = content
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=delta,
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
