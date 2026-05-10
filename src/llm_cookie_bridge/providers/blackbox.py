from __future__ import annotations

import re
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class BlackboxProvider(BaseProvider):
    """Blackbox AI web provider (www.blackbox.ai).

    Blackbox uses a cookie-based session plus a ``validated`` UUID token that is
    embedded in the frontend JavaScript bundle.  The token rotates occasionally;
    when it does you can grab a fresh value from DevTools → Network → any
    ``/api/chat`` request body → ``validated`` field.

    Authentication:

    1. Open https://www.blackbox.ai and start a chat (log in optional for basic
       models; required for premium ones).
    2. DevTools → Network → filter by ``/api/chat``
    3. From **Request Payload** copy the ``validated`` UUID.
    4. From **Request Headers** copy the ``Cookie`` header (look for
       ``sessionId=...`` and ``render_app_version_affinity=...``).

    Example::

        bridge = LLMCookieBridge.create(
            "blackbox",
            cookies={"sessionId": os.environ["BLACKBOX_SESSION_ID"]},
            validated=os.environ.get("BLACKBOX_VALIDATED", "00f37b34-a166-4efb-bce5-1312d87f2f94"),
        )

    Provider-specific chat options:

    * ``model`` – Agent/model name; defaults to ``"blackboxai"`` (Blackbox's own
      model).  Other common values: ``"gpt-4o"``, ``"claude-sonnet-3.5"``,
      ``"deepseek-chat"``, ``"meta-llama/Llama-3.3-70B-Instruct-Turbo"``.
    * ``chat_id`` – Optional chat session ID string for multi-turn context.
    * ``web_search`` – Enable web search grounding (default ``False``).
    """

    provider_name = "blackbox"
    default_base_url = "https://www.blackbox.ai"

    _CHAT_PATH = "/api/chat"
    _SETTINGS_PATH = "/api/check-agent-user-limit"

    # Known-good fallback validated token (may rotate; update from network trace)
    _DEFAULT_VALIDATED = "00f37b34-a166-4efb-bce5-1312d87f2f94"

    # Map of friendly model names to Blackbox agentMode ids
    _AGENT_MODELS: dict[str, dict[str, str]] = {
        "deepseek-v3": {"id": "deepseek-chat", "name": "DeepSeek-V3"},
        "deepseek-r1": {"id": "deepseek-reasoner", "name": "DeepSeek-R1"},
        "llama-3.3-70b": {
            "id": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "name": "Llama 3.3 70B",
        },
        "qwen-2.5-72b": {
            "id": "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "name": "Qwen 2.5 72B",
        },
    }

    DEFAULT_MODEL = "blackboxai"

    def __init__(
        self,
        *,
        validated: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._validated = validated or self._DEFAULT_VALIDATED

    async def _try_scrape_validated(self) -> str | None:
        """Try to scrape the validated token from the Blackbox homepage JS."""
        try:
            resp = await self.client.get("/", follow_redirects=True)
            text = resp.text
            for pattern in [
                r'"validated"\s*:\s*"([0-9a-f\-]{36})"',
                r'validated\s*=\s*["\']([0-9a-f\-]{36})',
                r'["\']([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})["\']',
            ]:
                m = re.search(pattern, text)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return None

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("ready") and not force:
            return
        # Try to refresh the validated token from the page
        fresh = await self._try_scrape_validated()
        if fresh:
            self._validated = fresh
        self._auth_state["ready"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        model = kwargs.get("model", self.DEFAULT_MODEL)
        chat_id = kwargs.get("chat_id") or random_uuid()
        web_search = kwargs.get("web_search", False)

        # Resolve agentMode
        agent_mode: dict[str, str] = {}
        if model in self._AGENT_MODELS:
            agent_mode = self._AGENT_MODELS[model]
        elif model not in ("blackboxai", "gpt-4o", "claude-sonnet-3.5"):
            # Treat as a custom agent ID
            agent_mode = {"id": model, "name": model}

        messages = [{"role": "user", "content": message}]

        payload: dict[str, Any] = {
            "messages": messages,
            "id": chat_id,
            "agentMode": agent_mode,
            "trendingAgentMode": {},
            "userSystemPrompt": None,
            "maxTokens": 1024,
            "isMemoryEnabled": False,
            "webSearchModePrompt": web_search,
            "imageGenerationMode": False,
            "validated": self._validated,
        }

        if model not in ("blackboxai",) and not agent_mode:
            payload["codeModelMode"] = False

        response = await self.request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "origin": self.base_url,
                "referer": f"{self.base_url}/",
            },
        )

        # Blackbox returns a plain-text or JSON response (not SSE)
        raw_text = response.text.strip()

        # Try to parse as JSON
        text_content = raw_text
        try:
            import json as _json
            data = _json.loads(raw_text)
            if isinstance(data, dict):
                text_content = (
                    data.get("response")
                    or data.get("choices", [{}])[0].get("message", {}).get("content")
                    or data.get("generations", [{}])[0].get("text")
                    or raw_text
                )
            elif isinstance(data, str):
                text_content = data
        except Exception:
            # Plain text response
            text_content = raw_text

        if not text_content:
            raise AuthenticationError(
                "Blackbox returned an empty response. "
                "Try refreshing your sessionId cookie or validated token."
            )

        # Emit single chunk (non-streaming)
        yield ChatChunk(
            provider=self.provider_name,
            text=text_content,
            delta=text_content,
            conversation_id=chat_id,
            raw={"text": text_content},
        )
        yield ChatChunk(
            provider=self.provider_name,
            text=text_content,
            delta="",
            done=True,
            conversation_id=chat_id,
        )
