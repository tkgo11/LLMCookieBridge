from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import random_uuid
from .base import BaseProvider


class CharacterAIProvider(BaseProvider):
    """Character.AI web provider (character.ai / neo.character.ai).

    Character.AI uses a bearer token extracted from your browser session.
    The primary chat API is WebSocket-based; this provider uses the HTTP
    REST interface at ``neo.character.ai`` instead, which is simpler and
    compatible with the existing ``httpx``-only architecture.

    Authentication: Extract your bearer token from a logged-in browser session.

    1. Open https://character.ai in Chrome/Firefox and log in.
    2. Open DevTools → Network tab.
    3. Refresh the page or start a chat.
    4. Find any request to ``plus.character.ai`` or ``neo.character.ai``.
    5. In the **Request Headers** copy the value after ``Authorization: Token ``.

    Example::

        bridge = LLMCookieBridge.create(
            "characterai",
            auth_token=os.environ["CHARACTERAI_TOKEN"],
            character_id="8_1NyR8w1dOXmI1uWaieQcd595jAxmbNqG5_84HLQkY",
        )

    Provider-specific chat options:

    * ``character_id`` – ID of the character to chat with.  Find it in the URL
      when chatting: ``character.ai/chat/<character_id>``.
    * ``chat_id`` – Continue an existing chat by its UUID. A new chat is created
      if omitted.
    * ``greeting`` – Whether to request the character's greeting when starting
      a new chat (default ``True``).
    """

    provider_name = "characterai"
    default_base_url = "https://neo.character.ai"

    _PLUS_BASE = "https://plus.character.ai"

    def __init__(
        self,
        *,
        auth_token: str | None = None,
        character_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if auth_token:
            self._auth_state["auth_token"] = auth_token
            self.client.headers["authorization"] = f"Token {auth_token}"
            self.client.headers["accept"] = "application/json"
            self.client.headers["content-type"] = "application/json"
        if character_id:
            self._auth_state["character_id"] = character_id

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("user_id") and not force:
            return
        token = self._auth_state.get("auth_token")
        if not token:
            raise AuthenticationError(
                "CharacterAI requires an auth_token. "
                "Log in at https://character.ai, open DevTools → Network, "
                "find any request to plus.character.ai and copy the "
                "'Authorization: Token ...' header value."
            )
        # Verify token by fetching user info
        response = await self.client.get(
            f"{self._PLUS_BASE}/chat/user/",
            headers={"authorization": f"Token {token}"},
        )
        if response.status_code == 401:
            raise AuthenticationError("CharacterAI token is invalid or expired.")
        if response.status_code >= 400:
            raise AuthenticationError(
                f"CharacterAI authentication failed: HTTP {response.status_code}"
            )
        try:
            data = response.json()
            user = data.get("user", {}).get("user", {})
            self._auth_state["user_id"] = user.get("id") or user.get("username", "")
            self._auth_state["name"] = user.get("name", "")
        except Exception:
            self._auth_state["user_id"] = "unknown"

    async def _get_or_create_chat(
        self, character_id: str, chat_id: str | None
    ) -> str:
        """Return an existing chat_id or create a new one."""
        if chat_id:
            return chat_id

        # Check for existing chats with this character
        try:
            resp = await self.client.get(
                f"{self.base_url}/chats/?character_ids={character_id}",
            )
            if resp.status_code == 200:
                data = resp.json()
                chats = data.get("chats") or []
                if chats:
                    return chats[0]["chat_id"]
        except Exception:
            pass

        # Create a new chat via REST (uses POST to neo.character.ai)
        new_chat_id = random_uuid()
        user_id = str(self._auth_state.get("user_id", ""))

        create_payload = {
            "chat": {
                "chat_id": new_chat_id,
                "creator_id": user_id,
                "visibility": "VISIBILITY_PRIVATE",
                "character_id": character_id,
                "type": "TYPE_ONE_ON_ONE",
            },
            "with_greeting": True,
        }

        resp = await self.client.post(
            f"{self.base_url}/chat/",
            content=json.dumps(create_payload),
            headers={"content-type": "application/json"},
        )
        if resp.status_code >= 400:
            # Fall back to just using the generated UUID
            return new_chat_id
        try:
            data = resp.json()
            chat = data.get("chat") or {}
            return chat.get("chat_id") or new_chat_id
        except Exception:
            return new_chat_id

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        character_id = (
            kwargs.get("character_id") or self._auth_state.get("character_id")
        )
        if not character_id:
            raise AuthenticationError(
                "CharacterAI requires a character_id. Pass it as a chat option or "
                "at construction time: LLMCookieBridge.create('characterai', "
                "auth_token=..., character_id='...')"
            )

        chat_id = kwargs.get("chat_id") or self._conversation_id
        chat_id = await self._get_or_create_chat(character_id, chat_id)
        self._conversation_id = chat_id

        user_id = str(self._auth_state.get("user_id", ""))
        candidate_id = random_uuid()
        turn_id = random_uuid()

        turn_payload = {
            "character_id": character_id,
            "num_candidates": 1,
            "previous_annotations": {
                "bad_memory": 0,
                "boring": 0,
                "ends_chat_early": 0,
                "funny": 0,
                "helpful": 0,
                "inaccurate": 0,
                "interesting": 0,
                "long": 0,
                "not_bad_memory": 0,
                "not_boring": 0,
                "not_ends_chat_early": 0,
                "not_funny": 0,
                "not_helpful": 0,
                "not_inaccurate": 0,
                "not_interesting": 0,
                "not_long": 0,
                "not_out_of_character": 0,
                "not_repetitive": 0,
                "not_short": 0,
                "out_of_character": 0,
                "repetitive": 0,
                "short": 0,
            },
            "selected_language": "",
            "tts_enabled": False,
            "turn": {
                "author": {
                    "author_id": user_id,
                    "is_human": True,
                    "name": "",
                },
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "raw_content": message,
                    }
                ],
                "primary_candidate_id": candidate_id,
                "turn_key": {
                    "chat_id": chat_id,
                    "turn_id": turn_id,
                },
            },
            "user_name": "",
        }

        # Use the streaming endpoint
        latest_text = ""

        async with self.stream_request(
            "POST",
            f"{self.base_url}/turn/candidate/",
            content=json.dumps(turn_payload),
            headers={
                "content-type": "application/json",
                "accept": "application/json",
            },
        ) as response:
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue

                # Character.AI returns newline-delimited JSON
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                turn = data.get("turn") or {}
                author = (turn.get("author") or {})
                if author.get("is_human"):
                    continue

                candidates = turn.get("candidates") or []
                if not candidates:
                    continue

                candidate = candidates[0]
                text = candidate.get("raw_content") or ""
                is_final = candidate.get("is_final", False)

                if text and text != latest_text:
                    delta = text[len(latest_text):]
                    latest_text = text
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=delta,
                        conversation_id=chat_id,
                        message_id=candidate.get("candidate_id"),
                        raw=data,
                    )

                if is_final:
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta="",
                        done=True,
                        conversation_id=chat_id,
                    )
                    return

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
