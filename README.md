# LLMCookieBridge

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.svg">
    <img alt="LLMCookieBridge logo" src="assets/logo-light.svg" width="860">
  </picture>
</p>

> Unified async Python access to major AI web apps using browser-session cookies instead of official API keys.

`llm-cookie-bridge` is a lightweight Python library that gives you a single async interface for talking to popular AI web apps through the same authenticated browser sessions you already use.

It currently supports:

- **Google Gemini web**
- **ChatGPT / OpenAI web**
- **Claude web**
- **Perplexity web**

This project is designed for engineers who need a **consistent chat + streaming abstraction** across multiple providers, but need to authenticate with **cookies or session-derived web tokens** rather than first-party API credentials.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [What this project is — and is not](#what-this-project-is--and-is-not)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Provider setup](#provider-setup)
  - [Gemini](#gemini)
  - [ChatGPT / OpenAI web](#chatgpt--openai-web)
  - [Claude](#claude)
  - [Perplexity](#perplexity)
- [Streaming](#streaming)
- [Refresh and session recovery](#refresh-and-session-recovery)
- [API overview](#api-overview)
- [Provider-specific chat options](#provider-specific-chat-options)
- [Error model](#error-model)
- [Security model](#security-model)
- [Testing](#testing)
- [Development](#development)
- [Research references](#research-references)
- [Publishing](#publishing)
- [License](#license)

---

## Why this exists

The major AI web apps all expose different internal request formats, auth bootstraps, and streaming behaviors. If you want to build tooling around the **web products** rather than the official APIs, you usually end up re-implementing the same plumbing repeatedly:

- turning browser cookies into authenticated requests
- discovering ephemeral web tokens
- normalizing SSE or frame-based streaming formats
- recovering from expired sessions
- keeping provider-specific parsing logic out of your application code

LLMCookieBridge packages that work into one minimal library with a stable Python interface.

---

## What this project is — and is not

### This project is

- a **unified async client** for multiple AI web products
- a **cookie/session bridge** for authenticated browser-backed access
- a good fit for **experimentation, internal tools, migration utilities, and research workflows**
- intentionally **small**, with only `httpx` as a runtime dependency

### This project is not

- an official SDK for any provider
- a compatibility promise for undocumented endpoints
- a production SLA surface
- a way to bypass provider terms, rate limits, billing, or account restrictions

> [!WARNING]
> This package targets reverse-engineered web endpoints that may change at any time and without notice. Treat it as an unstable bridge around consumer web products, not as a long-term guaranteed integration surface.

---

## Features

- **Unified provider interface** via `LLMCookieBridge.create(...)`
- **Async-first API** built on `httpx.AsyncClient`
- **Streaming support** with normalized chunk objects
- **Best-effort session refresh** for each provider
- **Custom refresh callbacks** for external cookie renewal flows
- **Minimal dependency footprint**
- **Pinned-host security defaults** for authenticated requests
- **Mock-transport-friendly design** for unit testing
- **Conversation continuity** where providers support it

---

## Installation

```bash
pip install llm-cookie-bridge
```

### Requirements

- Python **3.11+**
- An authenticated session for the target provider

---

## Quick start

```python
import asyncio
import os

from llm_cookie_bridge import LLMCookieBridge


async def main() -> None:
    bridge = LLMCookieBridge.create(
        "chatgpt",
        cookies={
            "__Secure-next-auth.session-token": os.environ["CHATGPT_SESSION_TOKEN"],
        },
    )

    async with bridge:
        response = await bridge.chat("Say hello in one sentence.")
        print(response.text)

        async for chunk in bridge.stream("Write a short poem about HTTP."):
            print(chunk.delta, end="", flush=True)


asyncio.run(main())
```

### What you get back

`chat()` returns a `ChatResponse`:

```python
@dataclass(slots=True)
class ChatResponse:
    provider: str
    text: str
    conversation_id: str | None
    message_id: str | None
    raw_events: list[Any]
    metadata: dict[str, Any]
```

`stream()` yields `ChatChunk` objects:

```python
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
```

---

## Provider setup

Each provider has slightly different authentication material and bootstrap behavior.

### Gemini

Expected cookies typically include:

- `__Secure-1PSID`
- `__Secure-1PSIDTS`

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "gemini",
    cookies={
        "__Secure-1PSID": os.environ["GEMINI_1PSID"],
        "__Secure-1PSIDTS": os.environ["GEMINI_1PSIDTS"],
    },
)
```

Under the hood, Gemini bootstrap extracts web app state such as:

- `SNlM0e` access token
- build label (`bl`)
- session id (`f.sid`)
- language metadata

### ChatGPT / OpenAI web

Expected cookie:

- `__Secure-next-auth.session-token`

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "chatgpt",
    cookies={
        "__Secure-next-auth.session-token": os.environ["CHATGPT_SESSION_TOKEN"],
    },
)
```

If you already have a valid web bearer token, you can also initialize directly with `access_token`:

```python
bridge = LLMCookieBridge.create(
    "chatgpt",
    access_token="...",
)
```

### Claude

Claude commonly works best with a full cookie header string, for example one containing `sessionKey=...`.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "claude",
    cookie_header=os.environ["CLAUDE_COOKIE_HEADER"],
)
```

During refresh, the bridge discovers the active Claude organization UUID automatically.

### Perplexity

Expected cookie:

- `__Secure-next-auth.session-token`

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "perplexity",
    cookies={
        "__Secure-next-auth.session-token": os.environ["PERPLEXITY_SESSION_TOKEN"],
    },
)
```

Perplexity performs a lightweight session-prime step before chat requests.

---

## Streaming

All providers are exposed through the same streaming interface:

```python
async with bridge:
    async for chunk in bridge.stream("Summarize this repo in three bullets."):
        if chunk.done:
            break
        print(chunk.delta, end="", flush=True)
```

### Streaming semantics

- `chunk.text` is the latest full accumulated text for that message
- `chunk.delta` is the newly added suffix when it can be derived
- the final yielded chunk has `done=True`
- `conversation_id` and `message_id` are preserved when the provider exposes them

---

## Refresh and session recovery

Every provider implements a best-effort `refresh()` flow:

- **Gemini**: reloads app bootstrap state and extracts required web tokens
- **ChatGPT**: fetches a bearer token from the web session endpoint
- **Claude**: discovers the active organization UUID
- **Perplexity**: re-primes the next-auth session endpoint

You can also provide a custom callback to renew cookies when a session expires.

### Simple refresh callback

```python
async def refresh_cookies(provider_name: str):
    assert provider_name == "claude"
    return {"sessionKey": "new-cookie-value"}


bridge = LLMCookieBridge.create(
    "claude",
    cookie_header="sessionKey=stale-cookie",
    refresh_callback=refresh_cookies,
)
```

### Rich refresh result

For more control, return `CookieRefreshResult`:

```python
from llm_cookie_bridge import CookieRefreshResult


async def refresh_session(provider_name: str) -> CookieRefreshResult:
    return CookieRefreshResult(
        cookies={"__Secure-next-auth.session-token": "fresh-cookie"},
        metadata={"source": "external-secret-store"},
    )
```

The callback may return:

- a plain `dict[str, str]` of cookies
- a `CookieRefreshResult`
- `None`

---

## API overview

### Factory

```python
bridge = LLMCookieBridge.create(
    provider,
    cookies=None,
    cookie_header=None,
    headers=None,
    timeout=30.0,
    transport=None,
    refresh_callback=None,
    allow_custom_base_url=False,
    follow_redirects=False,
    **provider_kwargs,
)
```

### Lifecycle

```python
async with bridge:
    ...

await bridge.aclose()
```

### Core methods

```python
await bridge.refresh(force=False)
await bridge.chat(message, **kwargs)
async for chunk in bridge.stream(message, **kwargs):
    ...
```

### Common constructor arguments

| Argument | Description |
| --- | --- |
| `cookies` | Cookie map passed into the underlying `httpx.AsyncClient` |
| `cookie_header` | Raw cookie header string, parsed and merged into cookies |
| `headers` | Additional request headers, sanitized against reserved auth-sensitive names |
| `timeout` | Request timeout in seconds |
| `transport` | Custom `httpx` transport, useful for tests and mocks |
| `refresh_callback` | Callback invoked on auth recovery paths |
| `allow_custom_base_url` | Required for cross-host authenticated overrides |
| `follow_redirects` | Disabled by default for safer authenticated behavior |

---

## Provider-specific chat options

These are forwarded through `bridge.chat(..., **kwargs)` and `bridge.stream(..., **kwargs)`.

### ChatGPT

| Option | Meaning |
| --- | --- |
| `conversation_id` | Continue an existing conversation |
| `parent_id` | Explicit parent message id |
| `model` | ChatGPT web model selector, defaults to `"auto"` |
| `disable_history` | Sets `history_and_training_disabled` |

Notes:

- The bridge remembers the last conversation/message id during the session.
- Follow-up turns reuse the last assistant message id automatically.

### Claude

| Option | Meaning |
| --- | --- |
| `conversation_id` | Continue an existing Claude conversation |
| `model` | Claude model id |
| `timezone` | Defaults to `"UTC"` |
| `attachments` | Attachment payload passthrough |
| `files` | File payload passthrough |

Notes:

- If no conversation exists, the bridge creates one automatically.
- Claude rate limit responses may raise `RateLimitError`.

### Gemini

Gemini currently exposes a minimal user-facing surface and derives the request envelope internally from the prompt and bootstrapped app state.

### Perplexity

| Option | Meaning |
| --- | --- |
| `mode` | `"auto"` or explicit non-auto mode |
| `incognito` | Whether to send an incognito flag |
| `language` | Defaults to `"en-US"` |
| `last_backend_uuid` | Continue from a previous backend state |
| `model_preference` | Perplexity model preference override |
| `sources` | Defaults to `["web"]` |
| `version` | Web request version string |
| `attachments` | Attachment payload passthrough |

---

## Error model

The public exception types are:

- `BridgeError` — base exception
- `AuthenticationError` — auth bootstrap or refresh failed
- `ProviderResponseError` — provider returned a non-2xx HTTP response
- `ParseError` — response could not be parsed
- `RateLimitError` — provider indicated usage or rate limiting

Example:

```python
from llm_cookie_bridge import AuthenticationError, LLMCookieBridge, RateLimitError

try:
    async with LLMCookieBridge.create("claude", cookie_header="sessionKey=...") as bridge:
        await bridge.chat("Hello")
except AuthenticationError:
    print("Session expired or cookies are invalid.")
except RateLimitError:
    print("Provider rate limit reached.")
```

---

## Security model

Because this library handles authenticated browser sessions, the defaults are intentionally strict.

### Built-in safeguards

- provider hosts are pinned by default
- cross-host base URL overrides are rejected unless `allow_custom_base_url=True`
- redirects are disabled by default
- user-supplied `authorization`, `cookie`, `host`, `origin`, and `referer` headers are rejected
- cookie maps are merged explicitly rather than blindly proxying a raw client config

### Operational guidance

- **Do not** feed untrusted input into `cookies`, `cookie_header`, `headers`, or `base_url`
- treat each bridge instance as **single-session and single-tenant**
- do not reuse one authenticated bridge across multiple end users
- expect provider-side auth, anti-abuse, or request-shape changes at any time

---

## Testing

The test suite uses mocked HTTP transports to lock down request shapes, auth flows, parser behavior, and security defaults.

Run tests locally:

```bash
pytest
```

What is currently covered:

- ChatGPT session bootstrap and conversation streaming
- follow-up turn parent message reuse
- Claude organization discovery and chat creation
- Gemini bootstrap token extraction and frame parsing
- Perplexity SSE answer extraction
- refresh callback behavior
- security defaults around base URLs and reserved headers

---

## Development

Clone the repo, create an environment, install dev dependencies, and run tests:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

### Design principles

- **Single abstraction, provider-specific internals**
- **Async by default**
- **Minimal dependencies**
- **Testable transports and parsers**
- **Secure defaults for authenticated traffic**

### Repository layout

```text
src/llm_cookie_bridge/
├── client.py         # public LLMCookieBridge entrypoint
├── exceptions.py     # public exception types
├── providers/        # provider implementations
├── sse.py            # SSE parsing helpers
├── types.py          # ChatChunk / ChatResponse / CookieRefreshResult
└── utils.py          # shared parsing and request utilities

tests/
└── ...               # provider and security regression tests
```

---

## Research references

These projects informed request shapes and auth bootstrap understanding, but are **not dependencies**:

- Gemini: `HanaokaYuzu/Gemini-API`
- ChatGPT: `acheong08/ChatGPT`, `lanqian528/chat2api`
- Claude: `Xerxes-2/clewdr`, `st1vms/unofficial-claude-api`, `KoushikNavuluri/Claude-API`
- Perplexity: `helallao/perplexity-ai`, `henrique-coder/perplexity-webui-scraper`, `nathanrchn/perplexityai`

---

## Publishing

This repository is configured for **PyPI Trusted Publishing** from GitHub Actions via:

- `.github/workflows/publish.yml`

To publish a release:

1. Configure the repository as a Trusted Publisher on PyPI
2. Create a GitHub Release
3. Let the publish workflow build and upload the new version automatically

---

## License

MIT
