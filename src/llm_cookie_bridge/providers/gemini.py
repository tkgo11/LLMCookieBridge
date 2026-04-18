from __future__ import annotations

import json
import random
import re
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, nested_get, parse_length_prefixed_json_frames
from .base import BaseProvider

DEFAULT_METADATA = ["", "", "", None, None, None, None, None, None, ""]


class GeminiProvider(BaseProvider):
    provider_name = "gemini"
    default_base_url = "https://gemini.google.com"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("access_token") and not force:
            return
        response = await self.client.get("/app")
        if response.status_code >= 400:
            raise AuthenticationError("Gemini bootstrap failed")
        text = response.text
        patterns = {
            "access_token": r'"SNlM0e":\s*"(.*?)"',
            "build_label": r'"cfb2h":\s*"(.*?)"',
            "session_id": r'"FdrFJe":\s*"(.*?)"',
            "language": r'"TuX5cc":\s*"(.*?)"',
            "push_id": r'"qKIAYe":\s*"(.*?)"',
        }
        extracted: dict[str, str] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                extracted[key] = match.group(1)
        if "access_token" not in extracted:
            raise AuthenticationError("Gemini SNlM0e token not found in app bootstrap")
        self._auth_state.update(extracted)

    def _build_inner_request(self, prompt: str) -> list[Any]:
        inner = [None] * 69
        inner[0] = [prompt, 0, None, None, None, None, 0]
        inner[1] = [self._auth_state.get("language", "en")]
        inner[2] = DEFAULT_METADATA
        inner[6] = [1]
        inner[7] = 1
        inner[10] = 1
        inner[11] = 0
        inner[17] = [[0]]
        inner[18] = 0
        inner[27] = 1
        inner[30] = [4]
        inner[41] = [1]
        inner[53] = 0
        inner[59] = random.randint(10**8, 10**9 - 1)
        inner[61] = []
        inner[68] = 2
        return inner

    def _extract_chunks(self, frames: list[Any], state: dict[str, str]) -> list[ChatChunk]:
        chunks: list[ChatChunk] = []
        for part in frames:
            inner_json = nested_get(part, [2])
            if not inner_json:
                continue
            try:
                part_json = json.loads(inner_json)
            except (TypeError, json.JSONDecodeError):
                continue
            candidate_list = nested_get(part_json, [4], []) or []
            cid = nested_get(part_json, [1, 0])
            rid = nested_get(part_json, [1, 1])
            for index, candidate in enumerate(candidate_list):
                candidate_id = nested_get(candidate, [0], f"candidate-{index}")
                text = nested_get(candidate, [1, 0], "") or ""
                if not text:
                    continue
                previous = state.get(candidate_id, "")
                delta = compute_delta(text, previous)
                state[candidate_id] = text
                chunks.append(
                    ChatChunk(
                        provider=self.provider_name,
                        text=text,
                        delta=delta,
                        conversation_id=cid,
                        message_id=rid,
                        raw=candidate,
                        metadata={"candidate_id": candidate_id},
                    )
                )
        return chunks

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()
        reqid = random.randint(10000, 99999)
        params = {"hl": self._auth_state.get("language", "en"), "_reqid": str(reqid), "rt": "c"}
        if build_label := self._auth_state.get("build_label"):
            params["bl"] = build_label
        if session_id := self._auth_state.get("session_id"):
            params["f.sid"] = session_id
        headers = {
            "content-type": "application/x-www-form-urlencoded;charset=utf-8",
            "origin": self.base_url,
            "referer": f"{self.base_url}/",
            "x-same-domain": "1",
        }
        data = {
            "at": self._auth_state["access_token"],
            "f.req": compact_json([None, compact_json(self._build_inner_request(message))]),
        }
        buffer = ""
        state: dict[str, str] = {}
        latest_text = ""
        conversation_id: str | None = None
        message_id: str | None = None
        async with self.stream_request(
            "POST",
            "/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate",
            params=params,
            headers=headers,
            data=data,
        ) as response:
            async for text in response.aiter_text():
                buffer += text
                frames, buffer = parse_length_prefixed_json_frames(buffer)
                for chunk in self._extract_chunks(frames, state):
                    latest_text = chunk.text or latest_text
                    conversation_id = chunk.conversation_id or conversation_id
                    message_id = chunk.message_id or message_id
                    yield chunk
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
            message_id=message_id,
        )
