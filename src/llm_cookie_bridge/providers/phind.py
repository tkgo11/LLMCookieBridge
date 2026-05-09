from __future__ import annotations

import json
import random
import time
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class PhindProvider(BaseProvider):
    """Phind web provider.

    Phind allows anonymous queries (no login required for basic use).  If you
    have a Phind account you can pass the ``next-auth.session-token`` cookie to
    get access to higher-tier models.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("phind")

    Example (authenticated)::

        bridge = LLMCookieBridge.create(
            "phind",
            cookies={"next-auth.session-token": os.environ["PHIND_SESSION_TOKEN"]},
        )

    Provider-specific chat options:

    * ``model`` – One of ``"Phind-70B"``, ``"Claude 3.5 Sonnet"``, ``"GPT-4o"``,
      etc.  Defaults to ``"Phind-70B"``.
    * ``message_history`` – List of ``{"role": ..., "content": ...}`` dicts for
      multi-turn context.
    * ``search`` – Whether to enable web search grounding (default ``False``).
    """

    provider_name = "phind"
    default_base_url = "https://www.phind.com"
    _api_base = "https://https.api.phind.com"

    DEFAULT_MODEL = "Phind-70B"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("anon_user_id") and not force:
            return
        # Phind works without auth – just generate a stable anon id.
        self._auth_state["anon_user_id"] = random_uuid()

    def _challenge(self) -> int:
        """Phind uses a simple numeric challenge (current unix timestamp * 9 % 10000)."""
        return int(time.time()) * 9 % 10000

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        message_history: list[dict[str, str]] = list(kwargs.get("message_history") or [])
        # Append current user turn.
        message_history.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "user_input": message,
            "message_history": message_history,
            "requested_model": model,
            "anon_user_id": self._auth_state["anon_user_id"],
            "challenge": self._challenge(),
            "search_mode": "auto" if kwargs.get("search", False) else "off",
            "language": "en",
        }

        latest_text = ""
        conversation_id = self._conversation_id or random_uuid()

        async with self._client.stream(
            "POST",
            f"{self._api_base}/agent/",
            content=compact_json(payload),
            headers={
                "content-type": "application/json;charset=UTF-8",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
                "accept": "text/event-stream",
            },
        ) as response:
            if response.status_code == 401:
                raise AuthenticationError("Phind authentication failed")
            if response.status_code >= 400:
                body = await response.aread()
                raise AuthenticationError(
                    f"Phind API error {response.status_code}: {body.decode(errors='ignore')[:300]}"
                )

            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    # Phind streams delta chunks with a "choices" array.
                    choices = obj.get("choices") or []
                    for choice in choices:
                        delta_obj = choice.get("delta") or {}
                        token = delta_obj.get("content", "")
                        if token:
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
