from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, random_uuid
from .base import BaseProvider


class TongyiProvider(BaseProvider):
    """Alibaba Tongyi Qianwen web provider (tongyi.aliyun.com).

    This uses Alibaba's internal Tongyi dialog API — the same endpoint that
    powers the tongyi.aliyun.com web chat frontend.  It is distinct from the
    official DashScope / Qwen REST API.

    Authentication: Extract the ``tongyi_sso_ticket`` cookie from a logged-in
    browser session at ``https://tongyi.aliyun.com``.

    1. Log in at https://tongyi.aliyun.com (requires Aliyun account)
    2. Open DevTools → Application → Cookies → tongyi.aliyun.com or aliyun.com
    3. Copy the value of ``tongyi_sso_ticket``
       (for accounts with login_aliyunid_ticket > 100 chars, use that instead)

    Example::

        bridge = LLMCookieBridge.create(
            "tongyi",
            cookies={"tongyi_sso_ticket": os.environ["TONGYI_SSO_TICKET"]},
        )

    Provider-specific chat options:

    * ``session_id`` – Continue an existing conversation session.
    * ``parent_msg_id`` – Parent message ID for threading.
    """

    provider_name = "tongyi"
    default_base_url = "https://qianwen.biz.aliyun.com"

    _CHAT_PATH = "/dialog/conversation"
    _SESSION_LIST_PATH = "/dialog/session/list"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Set required headers for Tongyi web API
        self.client.headers["x-platform"] = "pc_tongyi"
        self.client.headers["x-xsrf-token"] = "48b9ee49-a184-45e2-9f67-fa87213edcdc"
        self.client.headers["origin"] = "https://tongyi.aliyun.com"
        self.client.headers["referer"] = "https://tongyi.aliyun.com/"
        self.client.headers["content-type"] = "application/json"
        self.client.headers["accept"] = "text/event-stream"

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("primed") and not force:
            return
        # Verify cookie by hitting the session list endpoint
        cookies = dict(self.client.cookies)
        if not cookies.get("tongyi_sso_ticket") and not cookies.get("login_aliyunid_ticket"):
            raise AuthenticationError(
                "Tongyi requires 'tongyi_sso_ticket' cookie. "
                "Log in at https://tongyi.aliyun.com, open DevTools → "
                "Application → Cookies and copy tongyi_sso_ticket."
            )
        try:
            resp = await self.client.get(
                "https://tongyi.aliyun.com",
                follow_redirects=True,
            )
            if resp.status_code >= 400:
                raise AuthenticationError(
                    f"Tongyi session check failed: HTTP {resp.status_code}"
                )
        except Exception:
            pass
        self._auth_state["primed"] = True

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        session_id = kwargs.get("session_id") or self._conversation_id or ""
        parent_msg_id = kwargs.get("parent_msg_id") or self._message_id or ""
        request_id = random_uuid().replace("-", "")
        batch_id = random_uuid()

        payload: dict[str, Any] = {
            "mode": "chat",
            "model": "",
            "action": "next",
            "userAction": "chat",
            "requestId": request_id,
            "sessionId": session_id,
            "sessionType": "text_chat",
            "parentMsgId": parent_msg_id,
            "params": {
                "fileUploadBatchId": batch_id,
            },
            "contents": [
                {
                    "content": message,
                    "contentType": "text",
                    "role": "user",
                }
            ],
        }

        latest_text = ""
        new_session_id = session_id
        new_msg_id = parent_msg_id

        async with self.stream_request(
            "POST",
            self._CHAT_PATH,
            content=compact_json(payload),
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    # Extract metadata
                    msg_id = data.get("msgId", "")
                    session = data.get("sessionId", "")
                    if session:
                        new_session_id = session
                    if msg_id:
                        new_msg_id = msg_id

                    msg_status = data.get("msgStatus", "")

                    # Extract text content
                    contents = data.get("contents") or []
                    for item in contents:
                        if item.get("contentType") == "text" and item.get("role") == "assistant":
                            text = item.get("content") or ""
                            if text and text != latest_text:
                                delta = text[len(latest_text):]
                                latest_text = text
                                yield ChatChunk(
                                    provider=self.provider_name,
                                    text=latest_text,
                                    delta=delta,
                                    conversation_id=new_session_id,
                                    message_id=new_msg_id,
                                    raw=data,
                                )

                    if msg_status == "finished":
                        # Save state for multi-turn
                        self._conversation_id = new_session_id
                        self._message_id = new_msg_id
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta="",
                            done=True,
                            conversation_id=new_session_id,
                            message_id=new_msg_id,
                        )
                        return

        self._conversation_id = new_session_id
        self._message_id = new_msg_id
        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
            conversation_id=new_session_id,
        )
