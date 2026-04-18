from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

import httpx


@dataclass(slots=True)
class SSEEvent:
    event: str = "message"
    data: str = ""
    id: str | None = None
    retry: int | None = None


async def iter_sse(response: httpx.Response) -> AsyncIterator[SSEEvent]:
    event = SSEEvent()
    async for line in response.aiter_lines():
        if line == "":
            if event.data or event.event != "message":
                yield event
            event = SSEEvent()
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event.event = value
        elif field == "data":
            event.data = f"{event.data}\n{value}" if event.data else value
        elif field == "id":
            event.id = value
        elif field == "retry":
            try:
                event.retry = int(value)
            except ValueError:
                pass
    if event.data or event.event != "message":
        yield event
