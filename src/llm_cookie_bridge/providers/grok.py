from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class GrokProvider(BaseProvider):
    """Grok (grok.com) web provider.

    Authentication: Extract the following cookies from a logged-in browser
    session at ``https://grok.com``:

    * ``sso``
    * ``sso-rw``
    * ``x-anonuserid``
    * ``x-challenge``
    * ``x-signature``

    Example::

        bridge = LLMCookieBridge.create(
            "grok",
            cookies={
                "sso": os.environ["GROK_SSO"],
                "sso-rw": os.environ["GROK_SSO_RW"],
                "x-anonuserid": os.environ["GROK_ANONUSERID"],
                "x-challenge": os.environ["GROK_CHALLENGE"],
                "x-signature": os.environ["GROK_SIGNATURE"],
            },
        )

    Provider-specific chat options:

    * ``model`` – Grok model name, e.g. ``"grok-3"``, ``"grok-3-mini"``.
      Defaults to ``"grok-3"``.
    * ``disable_search`` – Disable web search grounding (default ``False``).
    * ``is_reasoning`` – Enable extended reasoning (default ``False``).
    * ``temporary`` – Send as a temporary conversation (default ``False``).
    * ``conversation_id`` – Continue from an existing conversation.
    """

    provider_name = "grok"
    default_base_url = "https://grok.com"

    DEFAULT_MODEL = "grok-3"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("ready") and not force:
            return
        # Grok uses cookies only – verify by hitting the root page.
        response = await self.client.get(
            "/",
            headers={"referer": "https://grok.com/"},
        )
        if response.status_code >= 400:
            raise AuthenticationError(
                f"Grok session bootstrap failed: HTTP {response.status_code}"
            )
        self._auth_state["ready"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        conversation_id = kwargs.get("conversation_id") or self._conversation_id

        payload: dict[str, Any] = {
            "temporary": kwargs.get("temporary", False),
            "modelName": model,
            "message": message,
            "fileAttachments": [],
            "imageAttachments": [],
            "disableSearch": kwargs.get("disable_search", False),
            "enableImageGeneration": False,
            "returnImageBytes": False,
            "returnRawGrokInXaiRequest": False,
            "enableImageStreaming": False,
            "imageGenerationCount": 0,
            "forceConcise": False,
            "toolOverrides": {},
            "enableSideBySide": False,
            "isPreset": False,
            "sendFinalMetadata": True,
            "customInstructions": "",
            "deepsearchPreset": "",
            "isReasoning": kwargs.get("is_reasoning", False),
        }

        if conversation_id:
            # Continue existing conversation.
            endpoint = f"/rest/app-chat/conversations/{conversation_id}/responses"
        else:
            # Start a new conversation.
            endpoint = "/rest/app-chat/conversations/new"

        latest_text = ""
        new_conversation_id = conversation_id

        async with self.stream_request(
            "POST",
            endpoint,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                result = obj.get("result") or {}
                resp_data = result.get("response") or {}

                # Final structured response.
                if "modelResponse" in resp_data:
                    model_resp = resp_data["modelResponse"]
                    final_text = model_resp.get("message", latest_text)
                    new_conversation_id = (
                        model_resp.get("conversationId")
                        or new_conversation_id
                        or random_uuid()
                    )
                    latest_text = final_text
                    continue

                # Conversation id may appear in early responses.
                cid = resp_data.get("conversationId") or result.get("conversationId")
                if cid:
                    new_conversation_id = cid

                # Streaming token.
                token = resp_data.get("token", "")
                if token:
                    latest_text += token
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=token,
                        conversation_id=new_conversation_id,
                        raw=obj,
                    )

        self._conversation_id = new_conversation_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=new_conversation_id,
        )
