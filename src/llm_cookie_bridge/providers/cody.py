from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json, openai_delta_text
from .base import BaseProvider


class CodyProvider(BaseProvider):
    """Sourcegraph Cody provider (sourcegraph.com web chat).

    Authentication: session cookies or an access token from a Sourcegraph
    account at https://sourcegraph.com.

    Example::

        bridge = LLMCookieBridge.create(
            "cody",
            auth_token=os.environ["SOURCEGRAPH_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"anthropic/claude-sonnet-4"``.
    * ``messages`` – Cody/OpenAI-style message list passthrough.
    """

    provider_name = "cody"
    default_base_url = "https://sourcegraph.com"

    _CHAT_PATH = "/.api/completions/stream"

    DEFAULT_MODEL = "anthropic/claude-sonnet-4"

    def __init__(self, *, auth_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"token {auth_token}"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("auth_token") and not force:
            return
        raise AuthenticationError(
            "Cody requires an auth_token (Sourcegraph access token or session)."
        )

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        messages = kwargs.get("messages") or [
            {"speaker": "human", "text": message},
        ]
        # Cody uses speaker/text pairs; accept OpenAI-style too.
        normalized = []
        for m in messages:
            if "speaker" in m:
                normalized.append(m)
            else:
                normalized.append({
                    "speaker": "human" if m.get("role") == "user" else "assistant",
                    "text": m.get("content", ""),
                })

        payload: dict[str, Any] = {
            "model": model,
            "messages": normalized,
            "maxTokensToSample": 4000,
            "temperature": 0.2,
            "topP": -1,
            "topK": -1,
            "stream": True,
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={"content-type": "application/json", "accept": "text/event-stream"},
        ) as response:
            async for obj in iter_sse_json(response):
                token = ""
                if isinstance(obj, dict):
                    token = obj.get("completion") or openai_delta_text(obj) or ""
                if not token:
                    continue
                # Cody streams cumulative completions
                if token.startswith(latest_text):
                    delta = token[len(latest_text):]
                    latest_text = token
                else:
                    delta = token
                    latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=delta,
                    raw=obj,
                )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
        )
