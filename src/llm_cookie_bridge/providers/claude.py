from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError, RateLimitError
from ..sse import iter_sse
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class ClaudeProvider(BaseProvider):
    provider_name = "claude"
    default_base_url = "https://claude.ai"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("organization_id") and not force:
            return
        response = await self.client.get("/api/organizations")
        if response.status_code >= 400:
            raise AuthenticationError("Claude organization discovery failed")
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise AuthenticationError("Claude organization list was empty")
        org_id = payload[0].get("uuid")
        if not org_id:
            raise AuthenticationError("Claude organization UUID missing")
        self._auth_state["organization_id"] = org_id

    async def _create_chat(self) -> str:
        org_id = self._auth_state["organization_id"]
        payload = {"name": "", "uuid": random_uuid()}
        response = await self.request(
            "POST",
            f"/api/organizations/{org_id}/chat_conversations",
            content=compact_json(payload),
            headers={"content-type": "application/json"},
        )
        data = response.json()
        chat_id = data.get("uuid") or payload["uuid"]
        self._conversation_id = chat_id
        return chat_id

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()
        org_id = self._auth_state["organization_id"]
        conversation_id = kwargs.get("conversation_id") or self._conversation_id or await self._create_chat()
        payload: dict[str, Any] = {
            "prompt": message,
            "timezone": kwargs.get("timezone", "UTC"),
            "attachments": kwargs.get("attachments", []),
            "files": kwargs.get("files", []),
        }
        if model := kwargs.get("model"):
            payload["model"] = model
        latest_text = ""
        async with self.stream_request(
            "POST",
            f"/api/organizations/{org_id}/chat_conversations/{conversation_id}/completion",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "referer": f"{self.base_url}/chat/{conversation_id}",
                "origin": self.base_url,
            },
        ) as response:
            async for event in iter_sse(response):
                if not event.data:
                    continue
                try:
                    item = json.loads(event.data)
                except json.JSONDecodeError:
                    continue
                if "error" in item:
                    error = item["error"]
                    if isinstance(error, dict) and error.get("resets_at"):
                        raise RateLimitError("Claude message rate limited")
                    raise AuthenticationError(f"Claude returned an error: {error}")
                completion = item.get("completion")
                if completion is None:
                    continue
                delta = compute_delta(completion, latest_text)
                latest_text = completion
                yield ChatChunk(
                    provider=self.provider_name,
                    text=completion,
                    delta=delta,
                    conversation_id=conversation_id,
                    raw=item,
                )
        self._conversation_id = conversation_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
        )
