from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable
from urllib.parse import urlparse

import httpx

from ..exceptions import AuthenticationError, ProviderResponseError
from ..types import ChatChunk, ChatResponse
from ..utils import merge_cookies, maybe_await, normalize_refresh_result, parse_cookie_header

RefreshCallback = Callable[[str], Awaitable[dict[str, str] | None] | dict[str, str] | None]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
RESERVED_HEADERS = {"authorization", "cookie", "host", "origin", "referer"}


def _validated_base_url(
    default_base_url: str,
    base_url: str | None,
    allow_custom_base_url: bool,
) -> str:
    if not base_url:
        return default_base_url
    if allow_custom_base_url:
        return base_url
    expected = urlparse(default_base_url)
    candidate = urlparse(base_url)
    if candidate.scheme != "https" or candidate.hostname != expected.hostname:
        raise ValueError(
            f"Refusing custom base_url for authenticated provider; expected https://{expected.hostname}"
        )
    return base_url


def _sanitize_headers(headers: dict[str, str] | None) -> dict[str, str]:
    sanitized = {"user-agent": DEFAULT_USER_AGENT}
    if not headers:
        return sanitized
    for key, value in headers.items():
        lower = key.lower()
        if lower in RESERVED_HEADERS:
            raise ValueError(f"Custom header '{key}' is reserved and cannot be overridden")
        sanitized[lower] = value
    return sanitized


class BaseProvider(ABC):
    provider_name = "base"
    default_base_url = ""

    def __init__(
        self,
        *,
        cookies: dict[str, str] | None = None,
        cookie_header: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        refresh_callback: RefreshCallback | None = None,
        allow_custom_base_url: bool = False,
        follow_redirects: bool = False,
    ) -> None:
        self.base_url = _validated_base_url(
            self.default_base_url,
            base_url,
            allow_custom_base_url,
        )
        self.refresh_callback = refresh_callback
        self._refresh_lock = asyncio.Lock()
        self._auth_state: dict[str, Any] = {}
        self._conversation_id: str | None = None
        self._message_id: str | None = None
        merged_cookies = merge_cookies(parse_cookie_header(cookie_header), cookies)
        merged_headers = _sanitize_headers(headers)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=merged_headers,
            cookies=merged_cookies,
            timeout=timeout,
            follow_redirects=follow_redirects,
            transport=transport,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._client.cookies.items())

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "BaseProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def _apply_refresh_callback(self) -> bool:
        if not self.refresh_callback:
            return False
        result = normalize_refresh_result(await maybe_await(self.refresh_callback(self.provider_name)))
        if result.cookie_header:
            self._client.cookies.update(parse_cookie_header(result.cookie_header))
        if result.cookies:
            self._client.cookies.update(result.cookies)
        if result.metadata:
            self._auth_state.update(result.metadata)
        return bool(result.cookie_header or result.cookies or result.metadata)

    async def ensure_authenticated(self, force: bool = False) -> None:
        if force or not self._auth_state:
            async with self._refresh_lock:
                if force or not self._auth_state:
                    try:
                        await self.refresh(force=force)
                    except AuthenticationError:
                        refreshed = await self._apply_refresh_callback()
                        if not refreshed:
                            raise
                        await self.refresh(force=True)

    @abstractmethod
    async def refresh(self, force: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(self, message: str, **kwargs: Any) -> AsyncIterator[ChatChunk]:
        raise NotImplementedError

    async def chat(self, message: str, **kwargs: Any) -> ChatResponse:
        latest_text = ""
        chunks: list[Any] = []
        conversation_id: str | None = None
        message_id: str | None = None
        metadata: dict[str, Any] = {}
        async for chunk in self.stream_chat(message, **kwargs):
            latest_text = chunk.text or latest_text
            conversation_id = chunk.conversation_id or conversation_id
            message_id = chunk.message_id or message_id
            metadata.update(chunk.metadata)
            chunks.append(chunk.raw if chunk.raw is not None else {"text": chunk.text, "done": chunk.done})
        return ChatResponse(
            provider=self.provider_name,
            text=latest_text,
            conversation_id=conversation_id,
            message_id=message_id,
            raw_events=chunks,
            metadata=metadata,
        )

    async def _recover_auth(self) -> None:
        refreshed = await self._apply_refresh_callback()
        await self.refresh(force=True)
        if not self._auth_state and not refreshed:
            raise AuthenticationError(f"Unable to recover {self.provider_name} authentication")

    async def request(
        self,
        method: str,
        url: str,
        *,
        retry_on_auth: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        response = await self._client.request(method, url, **kwargs)
        if retry_on_auth and response.status_code in {401, 403}:
            await response.aclose()
            await self._recover_auth()
            response = await self._client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise ProviderResponseError(self.provider_name, response.status_code, response.text[:500])
        return response

    @asynccontextmanager
    async def stream_request(
        self,
        method: str,
        url: str,
        *,
        retry_on_auth: bool = True,
        **kwargs: Any,
    ) -> AsyncIterator[httpx.Response]:
        async with self._client.stream(method, url, **kwargs) as response:
            if retry_on_auth and response.status_code in {401, 403}:
                await response.aread()
                await self._recover_auth()
            else:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ProviderResponseError(
                        self.provider_name,
                        response.status_code,
                        body.decode(errors="ignore")[:500],
                    )
                yield response
                return
        async with self._client.stream(method, url, **kwargs) as retry_response:
            if retry_response.status_code >= 400:
                body = await retry_response.aread()
                raise ProviderResponseError(
                    self.provider_name,
                    retry_response.status_code,
                    body.decode(errors="ignore")[:500],
                )
            yield retry_response
