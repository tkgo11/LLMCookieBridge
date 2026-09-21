from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_sse_json, openai_delta_text, openai_finish_reason
from .base import BaseProvider


class GitHubModelsProvider(BaseProvider):
    """GitHub Models provider (github.com/marketplace/models playground).

    The Models playground calls the Azure-hosted inference endpoint with a
    GitHub token (PAT or the ``github-models`` session bearer used by the
    marketplace playground).

    Example::

        bridge = LLMCookieBridge.create(
            "githubmodels",
            auth_token=os.environ["GITHUB_TOKEN"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"openai/gpt-4o-mini"``.
    * ``messages`` – Full OpenAI-style message list passthrough.
    """

    provider_name = "githubmodels"
    default_base_url = "https://models.github.ai"

    _CHAT_PATH = "/inference/chat/completions"

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
            "GitHubModels requires an auth_token (GitHub PAT or playground Bearer)."
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
                "x-github-model-catalog": "true",
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
