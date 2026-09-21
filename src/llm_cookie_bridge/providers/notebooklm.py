from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from ._common import iter_jsonl
from .base import BaseProvider


class NotebookLMProvider(BaseProvider):
    """Google NotebookLM provider (notebooklm.google.com).

    Authentication: full Google cookie header from a logged-in session at
    https://notebooklm.google.com.

    Example::

        bridge = LLMCookieBridge.create(
            "notebooklm",
            cookie_header=os.environ["GOOGLE_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``notebook_id`` – Chat against a specific notebook.
    """

    provider_name = "notebooklm"
    default_base_url = "https://notebooklm.google.com"

    _CHAT_PATH = "/api/chat"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        if not dict(self.client.cookies):
            raise AuthenticationError(
                "NotebookLM requires Google session cookies. "
                "Log in at https://notebooklm.google.com and export the cookie header."
            )
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        notebook_id = kwargs.get("notebook_id") or self._conversation_id or random_uuid()

        payload: dict[str, Any] = {
            "notebook_id": notebook_id,
            "query": message,
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
                    token = obj.get("text") or obj.get("answer") or ""
                    if not token and isinstance(obj.get("delta"), dict):
                        token = obj["delta"].get("text") or ""
                if not token:
                    continue
                latest_text += token
                yield ChatChunk(
                    provider=self.provider_name,
                    text=latest_text,
                    delta=token,
                    conversation_id=notebook_id,
                    raw=obj,
                )

        self._conversation_id = notebook_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=notebook_id,
        )
