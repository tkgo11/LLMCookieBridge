from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class SciraProvider(BaseProvider):
    """Scira AI provider (scira.ai) — open-source AI search engine.

    Scira exposes a Vercel-AI-SDK ``/api/search`` endpoint that streams
    data-protocol frames (``0:"<text>"`` lines).

    Example (anonymous)::

        bridge = LLMCookieBridge.create("scira")

    Provider-specific chat options:

    * ``model`` – Defaults to ``"scira-default"``.
    * ``group`` – Search group (``"web"``, ``"academic"``, etc.).
    """

    provider_name = "scira"
    default_base_url = "https://scira.ai"

    _CHAT_PATH = "/api/search"

    DEFAULT_MODEL = "scira-default"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        with contextlib.suppress(httpx.HTTPError):
            await self.client.get("/")
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        chat_id = kwargs.get("chat_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "id": chat_id,
            "messages": [{"role": "user", "content": message, "parts": [{"type": "text", "text": message}]}],
            "model": kwargs.get("model", self.DEFAULT_MODEL),
            "group": kwargs.get("group", "web"),
            "timezone": "UTC",
            "isCustomInstructionsEnabled": False,
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                # Vercel AI SDK data protocol: 0:"text chunk"
                token = ""
                if line.startswith("0:"):
                    try:
                        token = json.loads(line[2:])
                    except ValueError:
                        token = line[2:].strip('"')
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    conversation_id=chat_id,
                    raw=line,
                )

        self._conversation_id = chat_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
