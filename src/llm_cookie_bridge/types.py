from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CookieRefreshResult:
    cookies: dict[str, str] = field(default_factory=dict)
    cookie_header: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatChunk:
    provider: str
    text: str
    delta: str
    done: bool = False
    conversation_id: str | None = None
    message_id: str | None = None
    raw: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    provider: str
    text: str
    conversation_id: str | None = None
    message_id: str | None = None
    raw_events: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
