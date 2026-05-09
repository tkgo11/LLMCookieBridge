from __future__ import annotations

import json
import re
import uuid
from typing import Any, AsyncIterator

from ..exceptions import AuthenticationError
from ..types import ChatChunk
from ..utils import compact_json, compute_delta
from .base import BaseProvider


_GRAPH_DOC_ID = "7783822248314888"


class MetaAIProvider(BaseProvider):
    """Meta AI web provider (meta.ai).

    Works without authentication for anonymous queries in supported regions.
    For authenticated access (preserving history), pass your Meta browser
    cookies via ``cookie_header``.

    .. note::
        Meta AI may not be available in all countries.

    Example (anonymous)::

        bridge = LLMCookieBridge.create("meta")

    Example (authenticated)::

        bridge = LLMCookieBridge.create(
            "meta",
            cookie_header=os.environ["META_COOKIE_HEADER"],
        )

    Provider-specific chat options:

    * ``birthday`` – Date of birth string for anonymous TOS acceptance
      (default ``"1999-01-01"``). Only used for anonymous sessions.
    """

    provider_name = "meta"
    default_base_url = "https://www.meta.ai"

    # Tokens embedded in the page HTML
    _LSD_PATTERN = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"')
    _DTSG_PATTERN = re.compile(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"')
    _CSRF_PATTERN = re.compile(r'"abra_csrf":\{"value":"([^"]+)"')
    _DATR_PATTERN = re.compile(r'"datr":\{"value":"([^"]+)"')
    _JS_DATR_PATTERN = re.compile(r'"_js_datr":\{"value":"([^"]+)"')

    async def refresh(self, force: bool = False) -> None:
        if self._auth_state.get("ready") and not force:
            return
        # Fetch the Meta AI home page to collect required tokens.
        response = await self.client.get(
            "/",
            headers={"accept": "text/html,application/xhtml+xml"},
        )
        if response.status_code >= 400:
            raise AuthenticationError(
                f"Meta AI bootstrap failed: HTTP {response.status_code}"
            )
        text = response.text
        if "AbraGeoBlockedError" in text:
            raise AuthenticationError(
                "Meta AI is not available in your country/region."
            )

        def _extract(pattern: re.Pattern) -> str:
            m = pattern.search(text)
            return m.group(1) if m else ""

        lsd = _extract(self._LSD_PATTERN)
        dtsg = _extract(self._DTSG_PATTERN)
        csrf = _extract(self._CSRF_PATTERN)
        datr = _extract(self._DATR_PATTERN)
        js_datr = _extract(self._JS_DATR_PATTERN)

        if not lsd:
            raise AuthenticationError("Meta AI failed to extract LSD token from page")

        self._auth_state.update({
            "lsd": lsd,
            "dtsg": dtsg,
            "csrf": csrf,
            "datr": datr,
            "js_datr": js_datr,
            "ready": True,
            "access_token": None,
        })

        # For anonymous sessions, accept TOS to get an access_token.
        if not dict(self.client.cookies).get("c_user"):
            await self._accept_tos(lsd, csrf, datr, js_datr)

    async def _accept_tos(
        self,
        lsd: str,
        csrf: str,
        datr: str,
        js_datr: str,
        birthday: str = "1999-01-01",
    ) -> None:
        """Accept Terms of Service for anonymous users and store access_token."""
        payload = (
            f"lsd={lsd}"
            f"&fb_api_caller_class=RelayModern"
            f"&fb_api_req_friendly_name=useAbraAcceptTOSForTempUserMutation"
            f"&variables=%7B%22dob%22%3A%22{birthday}%22%2C%22icebreaker_type%22%3A%22TEXT%22%2C%22__relay_internal__pv__WebPixelRatiorelayprovider%22%3A1%7D"
            f"&doc_id=7604648749596940"
        )
        response = await self.client.post(
            "/api/graphql/",
            content=payload.encode(),
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "x-fb-friendly-name": "useAbraAcceptTOSForTempUserMutation",
                "x-fb-lsd": lsd,
                "x-asbd-id": "129477",
                "alt-used": "www.meta.ai",
            },
            cookies={
                "_js_datr": js_datr,
                "abra_csrf": csrf,
                "datr": datr,
            },
        )
        if response.status_code >= 400:
            # Non-fatal; proceed without access_token
            return
        try:
            data = response.json()
            token = (
                data["data"]["xab_abra_accept_terms_of_service"]
                ["new_temp_user_auth"]["access_token"]
            )
            self._auth_state["access_token"] = token
        except (KeyError, TypeError, ValueError):
            pass  # access_token optional; may still work without it

    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        await self.ensure_authenticated()

        lsd = self._auth_state["lsd"]
        dtsg = self._auth_state["dtsg"]
        access_token = self._auth_state.get("access_token")
        birthday = kwargs.get("birthday", "1999-01-01")

        variables = json.dumps({
            "message": {"sensitive_string_value": message},
            "externalConversationId": str(uuid.uuid4()),
            "offlineThreadingId": str(uuid.uuid4().int & ((1 << 64) - 1)),
            "suggestedPromptIndex": None,
            "flashVideoRecapInput": {"images": []},
            "flashPreviewInput": None,
            "promptPrefix": None,
            "entrypoint": "ABRA__CHAT__TEXT",
            "icebreaker_type": "TEXT",
            "__relay_internal__pv__AbraDebugDevOnlyrelayprovider": False,
            "__relay_internal__pv__WebPixelRatiorelayprovider": 1,
        })

        if access_token:
            url = "https://graph.meta.ai/graphql?locale=user"
            payload = (
                f"access_token={access_token}"
                f"&fb_api_caller_class=RelayModern"
                f"&fb_api_req_friendly_name=useAbraSendMessageMutation"
                f"&variables={variables}"
                f"&server_timestamps=true"
                f"&doc_id={_GRAPH_DOC_ID}"
            )
            extra_headers: dict[str, str] = {}
        else:
            url = f"{self.base_url}/api/graphql/"
            payload = (
                f"lsd={lsd}"
                f"&fb_dtsg={dtsg}"
                f"&fb_api_caller_class=RelayModern"
                f"&fb_api_req_friendly_name=useAbraSendMessageMutation"
                f"&variables={variables}"
                f"&server_timestamps=true"
                f"&doc_id={_GRAPH_DOC_ID}"
            )
            extra_headers = {"x-fb-lsd": lsd}

        from urllib.parse import quote
        # Re-encode variables properly
        payload_data = (
            f"variables={quote(variables)}"
            f"&server_timestamps=true"
            f"&doc_id={_GRAPH_DOC_ID}"
            f"&fb_api_caller_class=RelayModern"
            f"&fb_api_req_friendly_name=useAbraSendMessageMutation"
        )
        if access_token:
            payload_data = f"access_token={access_token}&" + payload_data
        else:
            payload_data = f"lsd={lsd}&fb_dtsg={dtsg}&" + payload_data

        request_headers = {
            "content-type": "application/x-www-form-urlencoded",
            "x-fb-friendly-name": "useAbraSendMessageMutation",
            "x-asbd-id": "129477",
            **extra_headers,
        }

        latest_text = ""

        async with self.stream_request(
            "POST",
            url,
            content=payload_data.encode(),
            headers=request_headers,
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                errors = obj.get("errors")
                if errors:
                    msgs = [e.get("message", "") for e in errors if isinstance(e, dict)]
                    raise AuthenticationError(f"Meta AI error: {'; '.join(msgs)}")

                bot_msg = (
                    (obj.get("data") or {})
                    .get("node", {})
                    .get("bot_response_message", {})
                )
                state = bot_msg.get("streaming_state")
                if state in ("STREAMING", "OVERALL_DONE"):
                    snippet = bot_msg.get("snippet", "")
                    if len(snippet) > len(latest_text):
                        delta = snippet[len(latest_text):]
                        latest_text = snippet
                        yield ChatChunk(
                            provider=self.provider_name,
                            text=latest_text,
                            delta=delta,
                            raw=obj,
                        )

        yield ChatChunk(
            provider=self.provider_name,
            text=latest_text,
            delta="",
            done=True,
        )
