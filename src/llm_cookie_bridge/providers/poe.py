from __future__ import annotations

import hashlib
import json
import re
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class PoeProvider(BaseProvider):
    """Poe.com web provider.

    Poe aggregates many LLMs (GPT-4o, Claude, Llama, Gemini, Mistral, etc.)
    behind a unified GraphQL + WebSocket interface.

    Authentication: Extract the following cookies from a logged-in browser
    session at ``https://poe.com``:

    * ``p-b`` – required session cookie
    * ``p-lat`` – required session cookie
    * ``formkey`` – optional; will be auto-fetched if missing (see below)

    To find them:
    1. Log in to https://poe.com
    2. Open DevTools → Application → Cookies → poe.com
    3. Copy ``p-b`` and ``p-lat``
    4. (Optional) For ``formkey``: Network tab → any ``gql_POST`` request →
       Headers → ``Poe-Formkey``

    Example::

        bridge = LLMCookieBridge.create(
            "poe",
            cookies={
                "p-b": os.environ["POE_P_B"],
                "p-lat": os.environ["POE_P_LAT"],
            },
        )

    Provider-specific chat options:

    * ``bot`` – The Poe bot handle/codename, e.g. ``"gpt4_o"``, ``"claude_3_igloo"``,
      ``"a2"``, ``"Llama-3.1-405B-Instruct"``.  Defaults to ``"gpt4_o"``.
    * ``chat_code`` – Continue a previous chat by its code (shown in the URL).
    * ``chat_id`` – Continue by numeric chat ID.
    """

    provider_name = "poe"
    default_base_url = "https://poe.com"

    _GQL_PATH = "/api/gql_POST"
    _SETTINGS_PATH = "/api/settings"
    _FORMKEY_SALT = "4LxgHM6KpFqokX0Ox"

    DEFAULT_BOT = "gpt4_o"

    # Query hashes from the Poe JS bundle.
    _QUERY_HASHES = {
        "SendMessageMutation": "f1486efc974a214dac6586c46b81bf631a95e58eab1d27b215f622859d74a23e",
        "ChatPageQuery": "e7dcf93e713a35a6b5642496b78339c9ef5ff0ae5e7e0c150ef534a738cced8c",
        "SubscriptionsMutation": "5a7bfc9ce3b4e456cd05a537cfa27096f08417593b8d9b53f57587f3b7b63e99",
        "HandleBotLandingPageQuery": "2997adcc7abe30f763da42eed3174b67fd1b60ac4a23dac794526448c2629a8d",
    }

    _SUBSCRIPTIONS_VARS = {
        "subscriptions": [
            {
                "subscriptionName": "messageAdded",
                "query": None,
                "queryHash": "993dcce616ce18788af3cce85e31437abf8fd64b14a3daaf3ae2f0e02d35aa03",
            },
            {
                "subscriptionName": "messageCancelled",
                "query": None,
                "queryHash": "14647e90e5960ec81fa83ae53d270462c3743199fbb6c4f26f40f4c83116d2ff",
            },
            {
                "subscriptionName": "chatTitleUpdated",
                "query": None,
                "queryHash": "ee062b1f269ecd02ea4c2a3f1e4b2f222f7574c43634a2da4ebeb616d8647e06",
            },
            {
                "subscriptionName": "viewerStateUpdated",
                "query": None,
                "queryHash": "3b2014dba11e57e99faa68b6b6c4956f3e982556f0cf832d728534f4319b92c7",
            },
        ]
    }

    def __init__(
        self,
        *,
        formkey: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if formkey:
            self._auth_state["formkey"] = formkey
            self.client.headers["poe-formkey"] = formkey

    def _gql_payload(self, query_name: str, variables: dict[str, Any]) -> str:
        return compact_json(
            {
                "queryName": query_name,
                "variables": variables,
                "extensions": {"hash": self._QUERY_HASHES[query_name]},
            }
        )

    def _tag_id(self, payload_str: str) -> str:
        formkey = self._auth_state.get("formkey", "")
        base = payload_str + formkey + self._FORMKEY_SALT
        return hashlib.md5(base.encode()).hexdigest()

    async def _gql(self, query_name: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = self._gql_payload(query_name, variables)
        response = await self.request(
            "POST",
            self._GQL_PATH,
            content=payload,
            headers={
                "content-type": "application/json",
                "poe-tag-id": self._tag_id(payload),
            },
        )
        return response.json()

    async def _fetch_formkey(self) -> str:
        """Extract the formkey from the Poe homepage JS/HTML."""
        resp = await self.client.get("/", follow_redirects=True)
        text = resp.text
        # Try multiple extraction patterns
        for pattern in [
            r'"formkey"\s*:\s*"([^"]+)"',
            r'formkey\s*=\s*"([^"]+)"',
            r'window\.ereNdsRqhp2Rd3LEW\s*=\s*["\']([^"\']+)',
        ]:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        # Fallback: call settings endpoint which also has formkey info
        resp2 = await self.client.get(self._SETTINGS_PATH)
        try:
            data = resp2.json()
            if "tchannelData" in data:
                # Settings endpoint doesn't give formkey but confirms auth
                pass
        except Exception:
            pass
        return ""

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("formkey") and not force:
            return
        # Check cookies
        cookies = dict(self.client.cookies)
        if not cookies.get("p-b") and not cookies.get("p-lat"):
            raise AuthenticationError(
                "Poe requires p-b and p-lat cookies. "
                "Log in at https://poe.com and copy them from DevTools → "
                "Application → Cookies."
            )
        # Auto-fetch formkey if not provided
        formkey = await self._fetch_formkey()
        if formkey:
            self._auth_state["formkey"] = formkey
            self.client.headers["poe-formkey"] = formkey
        else:
            raise AuthenticationError(
                "Could not auto-retrieve Poe formkey. "
                "Please provide it manually via the formkey= parameter."
            )

    async def _ensure_subscriptions(self) -> None:
        await self._gql("SubscriptionsMutation", self._SUBSCRIPTIONS_VARS)

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        bot = kwargs.get("bot", self.DEFAULT_BOT)
        chat_code = kwargs.get("chat_code") or self._auth_state.get("chat_code")
        chat_id = kwargs.get("chat_id") or self._auth_state.get("chat_id")

        # Build SendMessageMutation variables
        variables: dict[str, Any] = {
            "bot": bot,
            "query": message,
            "shouldFetchChat": True,
            "source": {
                "sourceType": "chat_input",
                "chatInputMetadata": {"useVoiceRecord": False},
            },
            "clientNonce": random_uuid().replace("-", "")[:16],
            "sdid": "",
            "attachments": [],
            "existingMessageAttachmentsIds": [],
            "messagePointsDisplayPrice": 0,
        }

        if chat_id:
            variables["chatId"] = chat_id
        else:
            variables["chatId"] = None

        # Send the message
        response_json = await self._gql("SendMessageMutation", variables)

        data = response_json.get("data") or {}
        edge_data = data.get("messageEdgeCreate") or {}
        status = edge_data.get("status", "")
        if status == "reached_limit":
            raise AuthenticationError(f"Poe daily limit reached for bot '{bot}'.")
        if status not in ("success", ""):
            status_msg = edge_data.get("statusMessage", "")
            raise AuthenticationError(
                f"Poe SendMessageMutation failed (status={status!r}): {status_msg}"
            )

        # Extract chat metadata for context
        chat_data = edge_data.get("chat") or {}
        new_chat_code = chat_data.get("chatCode") or chat_code
        new_chat_id = chat_data.get("chatId") or chat_id
        self._auth_state["chat_code"] = new_chat_code
        self._auth_state["chat_id"] = new_chat_id

        # Poll for the response via ChatPageQuery
        # (The older WebSocket approach requires websocket-client; we use HTTP polling here)
        latest_text = ""
        poll_attempts = 0
        max_polls = 60

        while poll_attempts < max_polls:
            poll_attempts += 1

            if new_chat_code:
                poll_vars = {"chatCode": new_chat_code}
            else:
                yield ChatChunk(
                    provider=self.provider_name,
                    text="",
                    delta="",
                    done=True,
                )
                return

            page_json = await self._gql("ChatPageQuery", poll_vars)
            page_data = page_json.get("data") or {}
            chat_obj = page_data.get("chatOfCode") or {}
            edges = (chat_obj.get("messagesConnection") or {}).get("edges") or []

            # Find the latest bot message
            for edge in reversed(edges):
                node = edge.get("node") or {}
                author = node.get("author", "")
                state = node.get("state", "")
                text = node.get("text") or ""

                # Skip human messages
                if author == "human":
                    continue

                if text and text != latest_text:
                    delta = text[len(latest_text):]
                    latest_text = text
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=delta,
                        conversation_id=str(new_chat_id) if new_chat_id else None,
                        raw=node,
                    )

                if state == "complete":
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta="",
                        done=True,
                        conversation_id=str(new_chat_id) if new_chat_id else None,
                    )
                    return

                if state and state.startswith("error"):
                    raise AuthenticationError(f"Poe message error: {state}")
                break  # Only process latest bot message per poll

            import asyncio
            await asyncio.sleep(0.5)

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
        )
