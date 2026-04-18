from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..sse import iter_sse
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class ChatGPTProvider(BaseProvider):
    provider_name = "chatgpt"
    default_base_url = "https://chatgpt.com"

    def __init__(self, *, access_token: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if access_token:
            self._auth_state["access_token"] = access_token
            self.client.headers["authorization"] = f"Bearer {access_token}"
            self.client.headers["accept"] = "text/event-stream"
            self.client.headers["content-type"] = "application/json"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("access_token") and not force:
            return
        response = await self.client.get("/api/auth/session")
        if response.status_code >= 400:
            raise AuthenticationError("ChatGPT session bootstrap failed")
        payload = response.json()
        token = payload.get("accessToken") or payload.get("access_token")
        if not token:
            raise AuthenticationError("ChatGPT access token not present in session response")
        self._auth_state["access_token"] = token
        self._auth_state["session"] = payload
        self.client.headers["authorization"] = f"Bearer {token}"
        self.client.headers["accept"] = "text/event-stream"
        self.client.headers["content-type"] = "application/json"

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()
        conversation_id = kwargs.get("conversation_id") or self._conversation_id
        parent_id = kwargs.get("parent_id") or self._message_id or random_uuid()
        payload = {
            "action": "next",
            "messages": [
                {
                    "id": random_uuid(),
                    "role": "user",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [message]},
                }
            ],
            "conversation_id": conversation_id,
            "parent_message_id": parent_id,
            "model": kwargs.get("model", "auto"),
            "history_and_training_disabled": kwargs.get("disable_history", False),
        }
        latest_text = ""
        latest_parent = parent_id
        async with self.stream_request(
            "POST",
            "/backend-api/conversation",
            content=compact_json(payload),
            headers={"content-type": "application/json"},
        ) as response:
            async for event in iter_sse(response):
                if event.data == "[DONE]":
                    break
                try:
                    item = json.loads(event.data)
                except json.JSONDecodeError:
                    continue
                message_obj = item.get("message") or {}
                author = (message_obj.get("author") or {}).get("role")
                if author != "assistant":
                    continue
                parts = ((message_obj.get("content") or {}).get("parts") or [])
                text = parts[0] if parts else ""
                if not text:
                    continue
                delta = compute_delta(text, latest_text)
                latest_text = text
                conversation_id = item.get("conversation_id") or conversation_id
                latest_parent = message_obj.get("id") or latest_parent
                self._conversation_id = conversation_id
                self._message_id = latest_parent
                yield ChatChunk(
                    provider=self.provider_name,
                    text=text,
                    delta=delta,
                    conversation_id=conversation_id,
                    message_id=latest_parent,
                    raw=item,
                    metadata={"finish_details": (message_obj.get("metadata") or {}).get("finish_details")},
                )
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
            message_id=latest_parent,
        )
