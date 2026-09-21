from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class DuckAIProvider(BaseProvider):
    """DuckDuckGo AI Chat provider (duck.ai / duckduckgo.com/aichat).

    DuckDuckGo's AI chat works anonymously — no account required.  The web
    client obtains a short-lived ``x-vqd-4`` token from a status endpoint and
    then sends chat requests against ``/duckchat/v1/chat``.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("duckai")

    Provider-specific chat options:

    * ``model`` – One of ``"gpt-4o-mini"``, ``"claude-3-haiku-20240307"``,
      ``"meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"``,
      ``"mistralai/Mistral-Small-24B-Instruct-2501"``, ``"o3-mini"``.
      Defaults to ``"gpt-4o-mini"``.
    """

    provider_name = "duckai"
    default_base_url = "https://duckduckgo.com"

    _STATUS_PATH = "/duckchat/v1/status"
    _CHAT_PATH = "/duckchat/v1/chat"

    DEFAULT_MODEL = "gpt-4o-mini"

    MODELS: ClassVar[list[str]] = [
        "gpt-4o-mini",
        "claude-3-haiku-20240307",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "mistralai/Mistral-Small-24B-Instruct-2501",
        "o3-mini",
    ]

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("vqd") and not force:
            return
        response = await self.client.get(
            self._STATUS_PATH,
            headers={
                "accept": "*/*",
                "x-vqd-accept": "1",
                "referer": "https://duckduckgo.com/aichat",
            },
        )
        token = response.headers.get("x-vqd-4")
        if not token:
            raise AuthenticationError(
                f"DuckAI could not obtain x-vqd-4 token: HTTP {response.status_code}"
            )
        self._auth_state["vqd"] = token

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        messages = kwargs.get("messages") or [{"role": "user", "content": message}]

        payload = {"model": model, "messages": messages}

        latest_text = ""
        vqd = self._auth_state.get("vqd", "")

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "x-vqd-4": vqd,
                "referer": "https://duckduckgo.com/aichat",
                "origin": "https://duckduckgo.com",
            },
        ) as response:
            new_vqd = response.headers.get("x-vqd-4")
            if new_vqd:
                self._auth_state["vqd"] = new_vqd
            async for obj in iter_sse_json(response):
                token = openai_delta_text(obj)
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    raw=obj,
                )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
        )
