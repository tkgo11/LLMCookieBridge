from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json
from .base import BaseProvider


class CohereProvider(BaseProvider):
    """Cohere provider (dashboard.cohere.com playground).

    Authentication: session cookies or the Bearer token from a logged-in
    Cohere dashboard session.

    Example::

        bridge = LLMCookieBridge.create(
            "cohere",
            auth_token=os.environ["COHERE_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"command-a-03-2025"``.
    * ``messages`` – Cohere v2 message list passthrough.
    """

    provider_name = "cohere"
    default_base_url = "https://api.cohere.com"

    _CHAT_PATH = "/v2/chat"

    DEFAULT_MODEL = "command-a-03-2025"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Cohere requires an auth_token (dashboard session Bearer or API key)."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        messages = kwargs.get("messages") or [{"role": "user", "content": message}]
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}

        latest_text = ""
        response_id: str | None = None

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={"content-type": "application/json", "accept": "text/event-stream"},
        ) as response:
            async for obj in iter_sse_json(response):
                if not isinstance(obj, dict):
                    continue
                if obj.get("id"):
                    response_id = obj["id"]
                token: Any = ""
                # Cohere v2 streams typed events: content-delta events carry text
                if obj.get("type") == "content-delta":
                    token = ((obj.get("delta") or {}).get("message") or {}).get("content") or {}
                    if isinstance(token, dict):
                        token = token.get("text") or ""
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    message_id=response_id,
                    raw=obj,
                )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            message_id=response_id,
        )
