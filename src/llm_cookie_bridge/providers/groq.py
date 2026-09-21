from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json, openai_delta_text, openai_finish_reason
from .base import BaseProvider


class GroqProvider(BaseProvider):
    """Groq provider (groq.com web playground).

    Authentication: a Groq API key, or the session Bearer token used by the
    groq.com web playground (DevTools → any ``chat/completions`` request →
    ``Authorization`` header).

    Example::

        bridge = LLMCookieBridge.create(
            "groq",
            auth_token=os.environ["GROQ_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"llama-3.3-70b-versatile"``.
    * ``messages`` – Full OpenAI-style message list passthrough.
    """

    provider_name = "groq"
    default_base_url = "https://api.groq.com"

    _CHAT_PATH = "/openai/v1/chat/completions"

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Bearer {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Groq requires an auth_token (API key or groq.com session Bearer)."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        messages = kwargs.get("messages") or [{"role": "user", "content": message}]
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]

        latest_text = ""
        response_id: str | None = None

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={"content-type": "application/json", "accept": "text/event-stream"},
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
