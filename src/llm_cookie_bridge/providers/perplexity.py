from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..sse import iter_sse
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class PerplexityProvider(BaseProvider):
    provider_name = "perplexity"
    default_base_url = "https://www.perplexity.ai"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        response = await self.client.get("/api/auth/session")
        if response.status_code < 400:
            try:
                self._auth_state["session"] = response.json()
            except ValueError:
                self._auth_state["session"] = {}
        self._auth_state["primed"] = True

    @staticmethod
    def _extract_text(item: dict[str, Any]) -> str:
        if isinstance(item.get("answer"), str) and item["answer"]:
            return item["answer"]
        if isinstance(item.get("output"), str) and item["output"]:
            return item["output"]
        text = item.get("text")
        parsed = text
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return text
        if isinstance(parsed, list):
            for step in parsed:
                if step.get("step_type") == "FINAL":
                    content = step.get("content", {})
                    answer = content.get("answer")
                    if isinstance(answer, str):
                        try:
                            answer_json = json.loads(answer)
                        except json.JSONDecodeError:
                            return answer
                        return answer_json.get("answer", "")
        return ""

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()
        mode = kwargs.get("mode", "auto")
        payload = {
            "query_str": message,
            "params": {
                "attachments": kwargs.get("attachments", []),
                "frontend_context_uuid": random_uuid(),
                "frontend_uuid": random_uuid(),
                "is_incognito": kwargs.get("incognito", False),
                "language": kwargs.get("language", "en-US"),
                "last_backend_uuid": kwargs.get("last_backend_uuid"),
                "mode": "concise" if mode == "auto" else "copilot",
                "model_preference": kwargs.get("model_preference", "turbo" if mode == "auto" else "pplx_pro"),
                "source": "default",
                "sources": kwargs.get("sources", ["web"]),
                "version": kwargs.get("version", "2.18"),
            },
        }
        latest_text = ""
        latest_backend_uuid = kwargs.get("last_backend_uuid")
        async with self.stream_request(
            "POST",
            "/rest/sse/perplexity_ask",
            content=compact_json(payload),
            headers={"content-type": "application/json", "accept": "text/event-stream"},
        ) as response:
            async for event in iter_sse(response):
                if event.event == "end_of_stream":
                    break
                if not event.data:
                    continue
                try:
                    item = json.loads(event.data)
                except json.JSONDecodeError:
                    continue
                text = self._extract_text(item)
                if not text:
                    continue
                delta = compute_delta(text, latest_text)
                latest_text = text
                latest_backend_uuid = item.get("backend_uuid") or latest_backend_uuid
                yield ChatChunk(
                    provider=self.provider_name,
                    text=text,
                    delta=delta,
                    conversation_id=latest_backend_uuid,
                    raw=item,
                )
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=latest_backend_uuid,
        )
