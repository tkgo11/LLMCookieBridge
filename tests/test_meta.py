"""Mock-transport tests for the Meta AI provider."""
from __future__ import annotations

import json

import httpx
import pytest

from llm_cookie_bridge import LLMCookieBridge


@pytest.mark.asyncio
async def test_meta_anonymous_tos_and_stream() -> None:
    """Meta AI with anonymous access: TOS failure falls back gracefully."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            html = (
                '"LSD",[],{"token":"lsd-token"}'
                '"DTSGInitialData",[],{"token":"dtsg-token"}'
                '"abra_csrf":{"value":"csrf-token"}'
                '"datr":{"value":"datr-token"}'
                '"_js_datr":{"value":"js-datr"}'
            )
            return httpx.Response(200, text=html)
        if request.url.path == "/api/graphql/":
            body = request.content.decode()
            if "useAbraAcceptTOSForTempUserMutation" in body:
                return httpx.Response(400, text="error")
            if "useAbraSendMessageMutation" in body:
                line1 = json.dumps(
                    {
                        "data": {
                            "node": {
                                "bot_response_message": {
                                    "streaming_state": "STREAMING",
                                    "snippet": "Hello Meta!",
                                }
                            }
                        }
                    }
                )
                line2 = json.dumps(
                    {
                        "data": {
                            "node": {
                                "bot_response_message": {
                                    "streaming_state": "OVERALL_DONE",
                                    "snippet": "Hello Meta!",
                                    "fetch_id": None,
                                }
                            }
                        }
                    }
                )
                return httpx.Response(200, text=line1 + "\n" + line2 + "\n")
            return httpx.Response(200, json={})
        raise AssertionError(f"Unexpected: {request.method} {request.url}")

    bridge = LLMCookieBridge.create(
        "meta",
        transport=httpx.MockTransport(handler),
    )
    async with bridge:
        response = await bridge.chat("hello")

    assert "Hello" in response.text


async def test_meta_token_extraction() -> None:
    """Verify LSD/DTSG token extraction from page HTML."""
    from llm_cookie_bridge.providers.meta import MetaAIProvider

    provider = MetaAIProvider()
    html = (
        '"LSD",[],{"token":"my-lsd-value"}'
        '"DTSGInitialData",[],{"token":"my-dtsg-value"}'
    )
    lsd_m = provider._LSD_PATTERN.search(html)
    dtsg_m = provider._DTSG_PATTERN.search(html)
    assert lsd_m and lsd_m.group(1) == "my-lsd-value"
    assert dtsg_m and dtsg_m.group(1) == "my-dtsg-value"
    await provider.close()


def test_meta_instantiation() -> None:
    bridge = LLMCookieBridge.create("meta")
    assert bridge.provider.provider_name == "meta"
