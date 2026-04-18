from __future__ import annotations

import inspect
import json
import re
import uuid
from difflib import SequenceMatcher
from typing import Any

from .types import CookieRefreshResult

_COOKIE_PAIR_RE = re.compile(r"\s*([^=;\s]+)=([^;]*)")
_FRAME_LENGTH_RE = re.compile(r"(\d+)\n")


def _utf16_prefix_length(text: str, units: int) -> int:
    count = 0
    used = 0
    while count < len(text) and used < units:
        char = text[count]
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > units:
            break
        used += width
        count += 1
    return count


def parse_cookie_header(cookie_header: str | None) -> dict[str, str]:
    if not cookie_header:
        return {}
    cookies: dict[str, str] = {}
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part:
            continue
        match = _COOKIE_PAIR_RE.match(part)
        if match:
            cookies[match.group(1)] = match.group(2)
    return cookies


def merge_cookies(*cookie_maps: dict[str, str] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for cookie_map in cookie_maps:
        if cookie_map:
            merged.update({k: v for k, v in cookie_map.items() if v is not None})
    return merged


def compact_json(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"))


def nested_get(data: Any, path: list[int | str], default: Any = None) -> Any:
    current = data
    for key in path:
        if isinstance(key, int):
            if isinstance(current, list) and -len(current) <= key < len(current):
                current = current[key]
                continue
            if isinstance(current, dict) and str(key) in current:
                current = current[str(key)]
                continue
            return default
        if isinstance(current, dict) and key in current:
            current = current[key]
            continue
        return default
    return default if current is None else current


def compute_delta(current: str, previous: str) -> str:
    if not previous:
        return current
    if current.startswith(previous):
        return current[len(previous) :]
    if previous in current:
        idx = current.rfind(previous)
        if idx != -1:
            return current[idx + len(previous) :]
    matcher = SequenceMatcher(None, previous, current)
    blocks = [block for block in matcher.get_matching_blocks() if block.size > 0]
    if blocks:
        block = blocks[-1]
        return current[block.b + block.size :]
    return current


def random_uuid() -> str:
    return str(uuid.uuid4())


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def normalize_refresh_result(value: Any) -> CookieRefreshResult:
    if isinstance(value, CookieRefreshResult):
        return value
    if isinstance(value, dict):
        return CookieRefreshResult(cookies=value)
    if value is None:
        return CookieRefreshResult()
    raise TypeError(f"Unsupported refresh callback result: {type(value)!r}")


def parse_length_prefixed_json_frames(buffer: str) -> tuple[list[Any], str]:
    content = buffer[4:] if buffer.startswith(")]}'") else buffer
    consumed = 0
    frames: list[Any] = []
    total = len(content)

    while consumed < total:
        while consumed < total and content[consumed].isspace():
            consumed += 1
        if consumed >= total:
            break
        match = _FRAME_LENGTH_RE.match(content, pos=consumed)
        if not match:
            break
        size = int(match.group(1))
        start = match.end()
        char_len = _utf16_prefix_length(content[start:], size)
        end = start + char_len
        if end > total:
            break
        chunk = content[start:end].strip()
        consumed = end
        if not chunk:
            continue
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            frames.extend(parsed)
        else:
            frames.append(parsed)
    return frames, content[consumed:]
