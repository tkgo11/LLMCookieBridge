from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


async def iter_sse_json(response: httpx.Response) -> AsyncIterator[Any]:
    """Yield parsed JSON objects from a ``data:``-style SSE response.

    Terminates early on the conventional ``data: [DONE]`` sentinel and skips
    non-JSON payload lines.
    """
    async for line in response.aiter_lines():
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw:
            continue
        if raw == "[DONE]":
            return
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


async def iter_jsonl(response: httpx.Response) -> AsyncIterator[Any]:
    """Yield parsed JSON objects from a newline-delimited JSON response."""
    async for line in response.aiter_lines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def openai_delta_text(obj: Any) -> str:
    """Extract the text delta from an OpenAI-style chat completion chunk."""
    if not isinstance(obj, dict):
        return ""
    choices = obj.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    choice = choices[0]
    delta = choice.get("delta") or choice.get("message") or {}
    if not isinstance(delta, dict):
        return ""
    return delta.get("content") or ""


def openai_finish_reason(obj: Any) -> str | None:
    """Return ``finish_reason`` from an OpenAI-style chunk, if present."""
    if not isinstance(obj, dict):
        return None
    choices = obj.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return None
    return choices[0].get("finish_reason")
