# LLMCookieBridge

`llm-cookie-bridge` is a unified async Python library for talking to major AI web apps using browser cookies or session-derived web tokens instead of official API keys.

> Warning
>
> This package targets reverse-engineered web endpoints that may change without notice. Treat it as an unstable bridge, not a production SLA surface.

## Implemented providers

- Google Gemini web
- ChatGPT / OpenAI web
- Claude web
- Perplexity web

## Design notes

- `httpx.AsyncClient` transport
- per-provider auth bootstrap + best-effort refresh
- unified async chat and streaming interface
- minimal dependencies
- unit-tested request builders and parsers with mocked transports
- secure defaults: provider hosts are pinned and redirects are disabled unless explicitly opted in

## Installation

```bash
pip install llm-cookie-bridge
```

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

        async for chunk in bridge.stream("Stream a short poem."):
            print(chunk.delta, end="", flush=True)

asyncio.run(main())
```

## Provider examples

### Gemini

```python
import os

bridge = LLMCookieBridge.create(
    "gemini",
    cookies={
        "__Secure-1PSID": os.environ["GEMINI_1PSID"],
        "__Secure-1PSIDTS": os.environ["GEMINI_1PSIDTS"],
    },
)
```

### ChatGPT / OpenAI web

```python
import os

bridge = LLMCookieBridge.create(
    "chatgpt",
    cookies={"__Secure-next-auth.session-token": os.environ["CHATGPT_SESSION_TOKEN"]},
)
```

### Claude

```python
import os

bridge = LLMCookieBridge.create(
    "claude",
    cookie_header=os.environ["CLAUDE_COOKIE_HEADER"],
)
```

### Perplexity

```python
import os

bridge = LLMCookieBridge.create(
    "perplexity",
    cookies={"__Secure-next-auth.session-token": os.environ["PERPLEXITY_SESSION_TOKEN"]},
)
```

## Auto refresh

Each provider exposes a best-effort `refresh()` implementation:

- Gemini reboots app state and extracts `SNlM0e`, `bl`, and `f.sid`
- ChatGPT re-fetches a bearer token from the web session endpoint when a next-auth cookie is present
- Claude re-discovers the organization UUID and can use a custom refresh callback for cookie renewal
- Perplexity re-primes the next-auth session endpoint and can use a custom refresh callback

You can also inject a custom refresh callback:

```python
async def refresh_cookies(provider_name: str):
    return {"sessionKey": "new-cookie-value"}

bridge = LLMCookieBridge.create(
    "claude",
    cookie_header=os.environ["CLAUDE_COOKIE_HEADER"],
    refresh_callback=refresh_cookies,
)
```

## Security notes

- Do not pass untrusted values into `cookies`, `cookie_header`, `headers`, or `base_url`.
- `base_url` overrides are pinned to the provider host by default; cross-host overrides require `allow_custom_base_url=True`.
- Custom `authorization`, `cookie`, `host`, `origin`, and `referer` headers are intentionally rejected.
- Treat each bridge/provider instance as single-session and single-tenant; do not reuse one instance across multiple users.

## API surface

- `await bridge.chat(message, **kwargs)`
- `async for chunk in bridge.stream(message, **kwargs)`
- `await bridge.refresh(force=True)`

## Research references

These informed the request shapes and auth bootstraps, but are **not dependencies**:

- Gemini: `HanaokaYuzu/Gemini-API`
- ChatGPT: `acheong08/ChatGPT`, `lanqian528/chat2api`
- Claude: `Xerxes-2/clewdr`, `st1vms/unofficial-claude-api`, `KoushikNavuluri/Claude-API`
- Perplexity: `helallao/perplexity-ai`, `henrique-coder/perplexity-webui-scraper`, `nathanrchn/perplexityai`
