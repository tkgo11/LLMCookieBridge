from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class PiProvider(BaseProvider):
    """Pi.ai web provider.

    Pi works without authentication for anonymous conversations.  If you have
    a Pi account you can pass session cookies to preserve conversation history.

    Pi requires browser-like headers for the initial handshake, so a standard
    browser User-Agent is essential.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("pi")

    Example (with account cookies)::

        bridge = LLMCookieBridge.create(
            "pi",
            cookie_header=os.environ["PI_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``conversation_id`` – Continue from a previous Pi conversation SID.
    * ``mode`` – ``"BASE"`` (default) or other Pi conversation modes.
    """

    provider_name = "pi"
    default_base_url = "https://pi.ai"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("conversation_id") and not force:
            return
        # Start a new conversation to prime the session.
        response = await self.client.post(
            "/api/chat/start",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "x-api-version": "3",
                "origin": self.base_url,
                "referer": f"{self.base_url}/talk",
            },
        )
        if response.status_code >= 400:
            raise AuthenticationError(
                f"Pi.ai session bootstrap failed: HTTP {response.status_code}"
            )
        try:
            data = response.json()
            sid = data["conversations"][0]["sid"]
        except (KeyError, IndexError, ValueError) as exc:
            raise AuthenticationError(f"Pi.ai session bootstrap failed: {exc}") from exc
        self._auth_state["conversation_id"] = sid

    async def _start_conversation(self) -> str:
        """Create a new Pi conversation and return the SID."""
        response = await self.request(
            "POST",
            "/api/chat/start",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "x-api-version": "3",
                "origin": self.base_url,
                "referer": f"{self.base_url}/talk",
            },
        )
        data = response.json()
        try:
            return data["conversations"][0]["sid"]
        except (KeyError, IndexError) as exc:
            raise AuthenticationError(f"Pi.ai conversation start failed: {data}") from exc

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        conversation_id = kwargs.get("conversation_id") or self._conversation_id
        if not conversation_id:
            conversation_id = await self._start_conversation()
            self._conversation_id = conversation_id

        payload = {
            "text": message,
            "conversation": conversation_id,
            "mode": kwargs.get("mode", "BASE"),
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
                "referer": f"{self.base_url}/talk",
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    raw = line[6:]
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    # Yield text tokens
                    token = obj.get("text", "")
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
