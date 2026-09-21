from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json
from ._common import iter_jsonl
from .base import BaseProvider


class AIStudioProvider(BaseProvider):
    """Google AI Studio provider (aistudio.google.com).

    Authentication: full Google cookie header from a logged-in session at
    https://aistudio.google.com (needs ``__Secure-1PSID`` and friends).

    Example::

        bridge = LLMCookieBridge.create(
            "aistudio",
            cookie_header=os.environ["GOOGLE_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``model`` – Defaults to ``"gemini-2.0-flash"``.
    """

    provider_name = "aistudio"
    default_base_url = "https://aistudio.google.com"

    _CHAT_PATH = "/api/GenerateFreeFormStream"

    DEFAULT_MODEL = "gemini-2.0-flash"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "AIStudio requires Google session cookies. "
                "Log in at https://aistudio.google.com and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)

        payload: dict[str, Any] = {
            "model": model,
            "contents": [{"role": "user", "parts": [{"text": message}]}],
            "generationConfig": {},
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
            async for obj in iter_jsonl(response):
                token = ""
                if isinstance(obj, dict):
                    token = obj.get("text") or ""
                    candidates = obj.get("candidates") or []
                    if not token and candidates and isinstance(candidates[0], dict):
                        content = candidates[0].get("content") or {}
                        parts = content.get("parts") or []
                        if parts and isinstance(parts[0], dict):
                            token = parts[0].get("text") or ""
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
