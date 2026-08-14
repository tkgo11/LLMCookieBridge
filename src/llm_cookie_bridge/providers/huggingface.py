from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, compute_delta, random_uuid
from .base import BaseProvider


class HuggingFaceProvider(BaseProvider):
    """HuggingFace Chat web provider.

    Authentication: Pass the ``hf-chat`` session cookie extracted from a logged-in
    browser session at ``https://huggingface.co/chat``.

    Example::

        bridge = LLMCookieBridge.create(
            "huggingface",
            cookies={"hf-chat": os.environ["HF_CHAT_COOKIE"]},
        )

    Provider-specific chat options:

    * ``model`` – HuggingFace model id, e.g.
      ``"meta-llama/Meta-Llama-3-70B-Instruct"``.  Defaults to the active
      model on the account.
    * ``system_prompt`` – System prompt for new conversations.
    * ``conversation_id`` – Continue an existing conversation.
    """

    provider_name = "huggingface"
    default_base_url = "https://huggingface.co"

    # A reasonable default – users can override via the ``model`` kwarg.
    DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("model_id") and not force:
            return
        # Prime the session so cookies are accepted, and discover the default
        # active model.
        response = await self.client.get("/chat")
        if response.status_code >= 400:
            raise AuthenticationError("HuggingFace Chat session bootstrap failed")
        # Fetch available models to confirm auth and get a valid model id.
        models_resp = await self.client.get(
            "/chat/api/v2/models",
            headers={"referer": f"{self.base_url}/chat"},
        )
        if models_resp.status_code >= 400:
            raise AuthenticationError(
                "HuggingFace Chat model list fetch failed – are cookies valid?"
            )
        try:
            models_data = models_resp.json()
            first_model = None
            if isinstance(models_data, list) and models_data:
                first_model = models_data[0].get("id")
            elif isinstance(models_data, dict):
                items = models_data.get("models") or models_data.get("data") or []
                if items:
                    first_model = items[0].get("id")
            self._auth_state["model_id"] = first_model or self.DEFAULT_MODEL
        except (AttributeError, IndexError, TypeError, ValueError):
            self._auth_state["model_id"] = self.DEFAULT_MODEL

    async def _create_conversation(self, model_id: str, system_prompt: str = "") -> str:
        """Create a new conversation and return its id."""
        payload: dict[str, Any] = {"model": model_id}
        if system_prompt:
            payload["preprompt"] = system_prompt
        response = await self.request(
            "POST",
            "/chat/conversation",
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "origin": self.base_url,
                "referer": f"{self.base_url}/chat",
            },
        )
        data = response.json()
        conversation_id = (
            data.get("conversationId")
            or data.get("id")
            or data.get("conversation_id")
        )
        if not conversation_id:
            raise AuthenticationError(
                "HuggingFace Chat failed to create conversation; response: "
                + json.dumps(data)[:200]
            )
        return conversation_id

    async def _get_root_message_id(self, conversation_id: str) -> str:
        """Retrieve the root message id for a conversation."""
        response = await self.request(
            "GET",
            f"/chat/api/v2/conversations/{conversation_id}",
            headers={"referer": f"{self.base_url}/chat/conversation/{conversation_id}"},
        )
        data = response.json()
        # The message tree root is typically the first item in the messages list.
        messages = data.get("messages") or []
        if messages:
            return messages[0].get("id") or random_uuid()
        return random_uuid()

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model_id = kwargs.get("model") or self._auth_state.get("model_id") or self.DEFAULT_MODEL
        system_prompt = kwargs.get("system_prompt", "")
        conversation_id = kwargs.get("conversation_id") or self._conversation_id

        if not conversation_id:
            conversation_id = await self._create_conversation(model_id, system_prompt)
            self._conversation_id = conversation_id

        # Retrieve the last message id to use as parent.
        parent_message_id = await self._get_root_message_id(conversation_id)

        req_body = {
            "id": parent_message_id,
            "inputs": message,
            "is_continue": False,
            "is_retry": False,
            "web_search": kwargs.get("web_search", False),
            "tools": [],
        }

        latest_text = ""
        message_id: str | None = None

        async with self.stream_request(
            "POST",
            f"/chat/conversation/{conversation_id}",
            content=b"data=" + compact_json(req_body).encode(),
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/chat/conversation/{conversation_id}",
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = obj.get("type")
                if event_type == "stream":
                    token = obj.get("token", "")
                    latest_text += token
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=latest_text,
                        delta=token,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        raw=obj,
                    )
                elif event_type == "finalAnswer":
                    final_text = obj.get("text", latest_text)
                    delta = compute_delta(final_text, latest_text)
                    latest_text = final_text
                    yield ChatChunk(
                        provider=self.provider_name,
                        text=final_text,
                        delta=delta,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        raw=obj,
                    )
                elif event_type == "messageId":
                    message_id = obj.get("messageId")
                elif event_type == "error":
                    raise AuthenticationError(
                        f"HuggingFace Chat error: {obj.get('message', obj)}"
                    )

        self._conversation_id = conversation_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=conversation_id,
            message_id=message_id,
        )
