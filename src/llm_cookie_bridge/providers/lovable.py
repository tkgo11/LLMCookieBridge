from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class LovableProvider(BaseProvider):
    """Lovable provider (lovable.dev).

    Authentication: session cookies from a Lovable account at
    https://lovable.dev.

    Example::

        bridge = LLMCookieBridge.create(
            "lovable",
            cookie_header=os.environ["LOVABLE_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``project_id`` – Chat within a specific project.
    """

    provider_name = "lovable"
    default_base_url = "https://lovable.dev"

    _CHAT_PATH = "/api/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "Lovable requires session cookies. "
                "Log in at https://lovable.dev and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        project_id = kwargs.get("project_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "project_id": project_id,
            "message": message,
            "messages": [{"role": "user", "content": message}],
        }

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
            },
        ) as response:
            async for obj in iter_sse_json(response):
                token = openai_delta_text(obj)
                if not token and isinstance(obj, dict):
                    token = obj.get("text") or obj.get("content") or ""
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    conversation_id=project_id,
                    raw=obj,
                )

        self._conversation_id = project_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=project_id,
        )
