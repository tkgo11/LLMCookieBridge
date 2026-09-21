from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json, openai_delta_text, openai_finish_reason
from .base import BaseProvider


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider (openrouter.ai).

    Authentication: an OpenRouter key or a session Bearer token copied from
    the openrouter.ai web chat (DevTools → any ``/api/v1/chat/completions``
    request → ``Authorization`` header).

    Example::

        bridge = LLMCookieBridge.create(
            "openrouter",
            auth_token=os.environ["OPENROUTER_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Any OpenRouter model id (defaults to
      ``"openai/gpt-4o-mini"``).
    * ``messages`` – Full OpenAI-style message list passthrough.
    """

    provider_name = "openrouter"
    default_base_url = "https://openrouter.ai"

    _CHAT_PATH = "/api/v1/chat/completions"

    DEFAULT_MODEL = "openai/gpt-4o-mini"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "OpenRouter requires an auth_token (API key or web session Bearer)."
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
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "http-referer": "https://openrouter.ai/chat",
                "x-title": "LLMCookieBridge",
            },
        ) as response:
            async for obj in iter_sse_json(response):
                if isinstance(obj, dict) and obj.get("id"):
                    response_id = obj["id"]
                token = openai_delta_text(obj)
                if token:
                    latest_text += token
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=token,
                        message_id=response_id,
                        raw=obj,
                    )
                if openai_finish_reason(obj) in ("stop", "length"):
                    break

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            message_id=response_id,
        )
