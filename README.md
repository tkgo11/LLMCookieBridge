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

It currently supports **61 providers**, grouped by category:

**Major AI web apps**

- **Google Gemini web** · **ChatGPT / OpenAI web** · **Claude web** · **Perplexity web** · **HuggingFace Chat web** · **Grok (xAI) web** · **DeepSeek web** · **You.com (YouChat) web** · **Pi.ai web** · **Meta AI web** · **Mistral Le Chat web** · **Microsoft Copilot web** · **Character.AI web** · **Google AI Studio** · **NotebookLM** · **DuckDuckGo AI Chat** · **Proton Lumo** · **Kagi Assistant**

**Aggregators & multi-model platforms**

- **Poe** _(GPT-4o, Claude, Llama, Gemini and 100+ bots)_ · **OpenRouter** · **Blackbox AI** _(OpenAI-compatible API)_ · **LM Arena** · **Monica** · **Sider** · **Merlin** · **PopAI** · **Genspark** · **Skywork** · **Wrtn** · **Abacus ChatLLM** · **Coze** · **Z.ai (GLM)**

**Chinese providers**

- **Qwen Chat** _(chat.qwen.ai)_ · **Tongyi Qianwen** _(now www.qianwen.com)_ · **Kimi (Moonshot)** · **Doubao (ByteDance)** · **Yuanbao (Tencent)** · **ChatGLM (Zhipu)** · **SparkDesk (iFlytek)** · **Hailuo (MiniMax)** · **SenseChat (SenseTime)** · **Baichuan** · **360 Zhinao**

**Search & research assistants**

- **Phind** · **iAsk** · **Scira** · **Komo** · **Andi** · **Felo** · **Devv**

**Developer & builder tools**

- **GitHub Models** · **Sourcegraph Cody** · **v0 (Vercel)** · **Bolt.new** · **Lovable** · **Websim** · **DeepAI**

**OpenAI-compatible APIs**

- **Groq** · **Together AI** · **Cohere** · **Venice AI**

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
  - [HuggingFace Chat](#huggingface-chat)
  - [Grok](#grok)
  - [Phind](#phind)
  - [DeepSeek](#deepseek)
  - [You.com](#youcom)
  - [Pi.ai](#piai)
  - [Meta AI](#meta-ai)
  - [Mistral Le Chat](#mistral-le-chat)
  - [Microsoft Copilot](#microsoft-copilot)
  - [Poe](#poe)
  - [Blackbox AI](#blackbox-ai)
  - [Character.AI](#characterai)
  - [Qwen Chat](#qwen-chat)
  - [Tongyi Qianwen](#tongyi-qianwen)
  - [Additional providers](#additional-providers)
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

### HuggingFace Chat

Expected cookie:

- `hf-chat`

Open `https://huggingface.co/chat` in a browser, log in, then copy the `hf-chat` cookie value from DevTools → Application → Cookies.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "huggingface",
    cookies={"hf-chat": os.environ["HF_CHAT_COOKIE"]},
)
```

During refresh the bridge primes the session and discovers the active model list from `/chat/api/v2/models`.

### Grok

Expected cookies (from https://grok.com):

- `sso`
- `sso-rw`
- `x-anonuserid`
- `x-challenge`
- `x-signature`

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "grok",
    cookies={
        "sso": os.environ["GROK_SSO"],
        "sso-rw": os.environ["GROK_SSO_RW"],
        "x-anonuserid": os.environ["GROK_ANONUSERID"],
        "x-challenge": os.environ["GROK_CHALLENGE"],
        "x-signature": os.environ["GROK_SIGNATURE"],
    },
)
```

### Phind

Phind allows anonymous queries without authentication. For full model access, pass the `next-auth.session-token` cookie.

```python
from llm_cookie_bridge import LLMCookieBridge

# Anonymous (no auth required)
bridge = LLMCookieBridge.create("phind")

# Authenticated
bridge = LLMCookieBridge.create(
    "phind",
    cookies={"next-auth.session-token": os.environ["PHIND_SESSION_TOKEN"]},
)
```

### DeepSeek

Extract the Bearer token from `localStorage` in a logged-in session at https://chat.deepseek.com.

In the browser console run:

```js
JSON.parse(localStorage.getItem("userToken")).value
```

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "deepseek",
    auth_token=os.environ["DEEPSEEK_AUTH_TOKEN"],
)
```

### You.com

You.com supports anonymous queries for default models. For access to custom models (GPT-4o, Claude, etc.), log in and export your browser cookies.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

# Anonymous
bridge = LLMCookieBridge.create("you")

# Authenticated
bridge = LLMCookieBridge.create(
    "you",
    cookie_header=os.environ["YOU_COOKIE_HEADER"],
)
```

### Pi.ai

Pi works without authentication for anonymous conversations. Pass cookies for account-linked sessions.

```python
from llm_cookie_bridge import LLMCookieBridge

# Anonymous
bridge = LLMCookieBridge.create("pi")

# Authenticated
bridge = LLMCookieBridge.create(
    "pi",
    cookie_header=os.environ["PI_COOKIE_HEADER"],
)
```

### Meta AI

Meta AI works without authentication in supported regions. For authenticated sessions, pass your Meta browser cookies.

> **Note**: Meta AI may be geo-blocked in some regions.

```python
from llm_cookie_bridge import LLMCookieBridge

# Anonymous
bridge = LLMCookieBridge.create("meta")

# Authenticated
bridge = LLMCookieBridge.create(
    "meta",
    cookie_header=os.environ["META_COOKIE_HEADER"],
)
```

### Mistral Le Chat

Log into https://chat.mistral.ai and export your session cookies.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "mistral",
    cookie_header=os.environ["MISTRAL_COOKIE_HEADER"],
)
```

### Microsoft Copilot

Log into https://copilot.microsoft.com and export the full cookie header string (including `_U`, `MUID`, and Microsoft auth cookies).

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "copilot",
    cookie_header=os.environ["COPILOT_COOKIE_HEADER"],
)
```

### Poe

Poe aggregates 100+ LLMs (GPT-4o, Claude, Llama, Gemini, Mistral, and more) behind a single interface.

**Required cookies:** `p-b` and `p-lat`

1. Log into https://poe.com
2. Open DevTools → Application → Cookies → poe.com
3. Copy the values of `p-b` and `p-lat`
4. *(Optional)* For `formkey`: Network tab → any `gql_POST` request → Headers → `Poe-Formkey`

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "poe",
    cookies={
        "p-b": os.environ["POE_P_B"],
        "p-lat": os.environ["POE_P_LAT"],
    },
    # Optional – will be auto-fetched if omitted:
    # formkey=os.environ["POE_FORMKEY"],
)

# Chat with a specific bot (default is gpt4_o)
async with bridge:
    response = await bridge.chat("What is quantum computing?", bot="claude_3_igloo")
    print(response.text)
```

### Blackbox AI

Blackbox pivoted from a cookie-based web chat to an **OpenAI-compatible inference API** at `api.blackbox.ai/chat/completions`.

**Required:** an API key — sign in at https://www.blackbox.ai and create one from the dashboard.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "blackbox",
    auth_token=os.environ["BLACKBOX_API_KEY"],
)

async with bridge:
    response = await bridge.chat("Explain transformers in ML")

    # Any model on the platform, e.g.
    response = await bridge.chat(
        "Write a Python sorting algorithm",
        model="blackboxai/deepseek/deepseek-chat",
    )
    print(response.text)
```

### Character.AI

Character.AI hosts thousands of AI characters with distinct personalities.

**Required:** Bearer token from your logged-in session.

1. Log into https://character.ai in your browser
2. Open DevTools → Network tab
3. Reload the page or start a chat
4. Find any request to `plus.character.ai` or `neo.character.ai`
5. Copy the `Authorization: Token <value>` header value

**Finding a character ID:** The character ID appears in the URL when you open a chat: `https://character.ai/chat/<character_id>`

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "characterai",
    auth_token=os.environ["CHARACTERAI_TOKEN"],
    character_id="8_1NyR8w1dOXmI1uWaieQcd595jAxmbNqG5_84HLQkY",  # example
)

async with bridge:
    response = await bridge.chat("Tell me a story about dragons")
    print(response.text)
```

### Qwen Chat

Alibaba's Qwen Chat web interface (chat.qwen.ai). Auth token from `localStorage.getItem("token")` in the browser console, or the `Authorization: Bearer` header of any `completions` network request.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "qwen",
    auth_token=os.environ["QWEN_AUTH_TOKEN"],
)

async with bridge:
    response = await bridge.chat("Explain quantum computing", model="qwen-max-latest")
    print(response.text)
```

### Tongyi Qianwen

Tongyi Qianwen (通义千问) was merged into the unified **Qianwen** web app at https://www.qianwen.com — the Chinese counterpart of chat.qwen.ai — sharing the same internal v2 API. The old `qianwen.biz.aliyun.com` API is gone. Requires an Alibaba account.

**Getting your token:** Log in at https://www.qianwen.com → browser console → `localStorage.getItem("token")`, or copy the `Authorization: Bearer` header of any `completions` request in DevTools.

```python
import os
from llm_cookie_bridge import LLMCookieBridge

bridge = LLMCookieBridge.create(
    "tongyi",
    auth_token=os.environ["TONGYI_AUTH_TOKEN"],
)

async with bridge:
    response = await bridge.chat("你好！请介绍一下自己。")
    print(response.text)
```

### Additional providers

The remaining providers follow the same `LLMCookieBridge.create(name, ...)` pattern.
Auth material is one of: `auth_token` (Bearer/API key), `cookie_header`/`cookies`
(browser session), or none (anonymous).

| `create()` name | Site | Auth | Notes |
| --- | --- | --- | --- |
| `duckai` | duckduckgo.com | none | Anonymous; fetches `x-vqd-4` token automatically |
| `zai` | chat.z.ai | `auth_token` or none | Falls back to guest token when unauthenticated |
| `kimi` | kimi.com | `auth_token` | Moonshot AI; `localStorage` access token |
| `lmarena` | lmarena.ai | none | Anonymous arena chat |
| `openrouter` | openrouter.ai | `auth_token` | OpenAI-compatible; any OpenRouter model id |
| `groq` | api.groq.com | `auth_token` | OpenAI-compatible; e.g. `llama-3.3-70b-versatile` |
| `together` | api.together.xyz | `auth_token` | OpenAI-compatible |
| `githubmodels` | models.github.ai | `auth_token` | GitHub PAT with `models:read` |
| `doubao` | doubao.com | cookies | ByteDance; `sessionid` cookie |
| `yuanbao` | yuanbao.tencent.com | cookies | Tencent Hunyuan web |
| `chatglm` | chatglm.cn | `auth_token` | Zhipu GLM web token |
| `sparkdesk` | xinghuo.xfyun.cn | cookies | iFlytek Spark web |
| `hailuo` | hailuo.ai | `auth_token` | MiniMax web token |
| `iask` | iask.ai | none | Anonymous search chat |
| `scira` | scira.ai | none | Anonymous; Vercel data-protocol stream |
| `komo` | komo.ai | none | Anonymous search chat |
| `andi` | andisearch.com | none | Anonymous search chat |
| `felo` | felo.ai | none | Anonymous search chat |
| `devv` | devv.ai | none | Anonymous dev-focused search |
| `venice` | venice.ai | none | Anonymous; privacy-focused inference |
| `deepai` | deepai.org | none | Anonymous chat |
| `aistudio` | aistudio.google.com | cookies | Google account cookies |
| `notebooklm` | notebooklm.google.com | cookies | Google account cookies |
| `cohere` | api.cohere.com | `auth_token` | Cohere v2 chat API |
| `lumo` | lumo.proton.me | cookies | Proton session cookies |
| `v0` | v0.dev | cookies | Vercel v0 chat |
| `bolt` | bolt.new | none | StackBlitz Bolt chat |
| `lovable` | lovable.dev | cookies | Lovable builder session |
| `websim` | websim.ai | `auth_token` | Websim API key |
| `monica` | monica.im | cookies | Monica assistant session |
| `sider` | sider.ai | cookies | Sider assistant session |
| `merlin` | getmerlin.in | cookies | Merlin assistant session |
| `popai` | popai.pro | cookies | PopAI session |
| `genspark` | genspark.ai | cookies | Genspark session |
| `skywork` | skywork.ai | cookies | Skywork session |
| `sensechat` | chat.sensetime.com | `auth_token` | SenseTime web token |
| `baichuan` | baichuan-ai.com | cookies | Baichuan web session |
| `wrtn` | wrtn.ai | cookies | Korean aggregator session |
| `coze` | coze.com | cookies | ByteDance bot platform; pass `bot_id` |
| `kagi` | kagi.com | cookies | Paid Kagi account (Assistant) |
| `cody` | sourcegraph.com | `auth_token` | Sourcegraph access token |
| `ai360` | bot.n.cn | cookies | 360 Zhinao session |
| `abacus` | apps.abacus.ai | cookies | ChatLLM session |

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
- **HuggingFace Chat**: re-primes the session and refreshes the model list
- **Grok**: verifies cookie-based session by pinging the root page
- **Phind**: generates a stable anonymous user ID
- **DeepSeek**: validates the Bearer auth token is present
- **You.com**: verifies connectivity to the You.com home page
- **Pi.ai**: starts a new conversation to prime the session
- **Meta AI**: fetches the home page to extract LSD/DTSG tokens and (for anonymous sessions) accepts ToS
- **Mistral Le Chat**: verifies session by loading the home page
- **Microsoft Copilot**: primes the session by loading the home page
- **Poe**: fetches formkey from the Poe home page
- **Blackbox AI**: validates that an API key is present
- **Character.AI**: verifies the bearer token by fetching the authenticated user profile
- **Qwen Chat**: validates that an auth token is present
- **Tongyi Qianwen**: validates that a Bearer token is present
- **New providers**: token providers validate the token; cookie providers check session cookies; anonymous providers prime lightweight session state (e.g. DuckAI's `x-vqd-4` token or Z.ai's guest token)

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

### HuggingFace Chat

| Option | Meaning |
| --- | --- |
| `model` | HuggingFace model id, e.g. `"meta-llama/Meta-Llama-3.1-70B-Instruct"` |
| `system_prompt` | System prompt injected when creating a new conversation |
| `conversation_id` | Continue an existing conversation |
| `web_search` | Enable the HuggingFace web-search tool (default `False`) |

Notes:

- If no conversation exists, the bridge creates one automatically via `POST /chat/conversation`.
- The active model is auto-discovered from `/chat/api/v2/models` on first use.

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

### Grok

| Option | Meaning |
| --- | --- |
| `model` | Grok model name, e.g. `"grok-3"`, `"grok-3-mini"`. Defaults to `"grok-3"` |
| `disable_search` | Disable web search grounding (default `False`) |
| `is_reasoning` | Enable extended reasoning (default `False`) |
| `temporary` | Send as a temporary conversation (default `False`) |
| `conversation_id` | Continue an existing conversation |

### Phind

| Option | Meaning |
| --- | --- |
| `model` | One of `"Phind-70B"` (default), `"Claude 3.5 Sonnet"`, `"GPT-4o"`, etc. |
| `message_history` | List of `{"role": ..., "content": ...}` dicts for multi-turn context |
| `search` | Enable web search grounding (default `False`) |

### DeepSeek

| Option | Meaning |
| --- | --- |
| `model` | `"deepseek_chat"` (default) or `"deepseek_reasoner"` |
| `thinking_enabled` | Enable extended reasoning / thinking (default `False`) |
| `search_enabled` | Enable web search grounding (default `False`) |
| `parent_message_id` | Parent message ID for threading |
| `conversation_id` | Continue an existing chat session |

Notes:

- A new chat session is created automatically on first use.
- The bridge tracks `conversation_id` and `message_id` across turns.

### You.com

| Option | Meaning |
| --- | --- |
| `model` | Model alias: `"gpt-4o"`, `"claude-3.5-sonnet"`, `"llama-3.3-70b"`, etc. |
| `chat_mode` | `"default"` \| `"custom"` \| `"create"` \| `"agent"`. Inferred from model when not set |
| `chat_id` | Re-use a previous chat UUID |

### Pi.ai

| Option | Meaning |
| --- | --- |
| `conversation_id` | Continue from a previous Pi conversation SID |
| `mode` | `"BASE"` (default) or other Pi conversation modes |

Notes:

- A new conversation is created automatically on first use.

### Meta AI

| Option | Meaning |
| --- | --- |
| `birthday` | Date of birth for anonymous TOS acceptance (default `"1999-01-01"`) |

Notes:

- For anonymous sessions, the bridge automatically accepts Terms of Service.
- May not be available in all countries/regions.

### Mistral Le Chat

| Option | Meaning |
| --- | --- |
| `model` | Mistral model ID: `"mistral-large-latest"` (default), `"mistral-small-latest"`, `"codestral-latest"` |
| `conversation_id` | Continue an existing conversation UUID |
| `system_prompt` | System prompt for new conversations |

Notes:

- A new conversation is created automatically on first use.

### Microsoft Copilot

| Option | Meaning |
| --- | --- |
| `conversation_id` | Continue an existing Copilot conversation |
| `tone` | `"Balanced"` (default), `"Creative"`, `"Precise"` |
| `locale` | Language locale tag (default `"en-US"`) |

### Poe

| Option | Meaning |
| --- | --- |
| `bot` | Bot codename (default `"gpt4_o"`). Examples: `"a2"`, `"claude_3_igloo"`, `"Llama-3.1-405B"` |
| `chat_code` | Chat code from URL to continue an existing thread |
| `chat_id` | Numeric chat ID to continue an existing thread |

### Blackbox AI

| Option | Meaning |
| --- | --- |
| `model` | Model/agent name (default `"blackboxai"`). Aliases: `"deepseek-v3"`, `"deepseek-r1"`, `"llama-3.3-70b"`, `"qwen-2.5-72b"` |
| `chat_id` | Session UUID for multi-turn context (auto-generated if not provided) |
| `web_search` | Enable web search grounding (default `False`) |

### Character.AI

| Option | Meaning |
| --- | --- |
| `character_id` | **Required.** ID of the character (from chat URL or search) |
| `chat_id` | Reuse an existing chat UUID |
| `greeting` | Request a greeting when starting a new chat (default `True`) |

### Qwen Chat

| Option | Meaning |
| --- | --- |
| `model` | Model name (default `"qwen-plus-latest"`). Options: `"qwen-max-latest"`, `"qwen-turbo-latest"`, `"qwq-32b"` |
| `web_search` | Enable web search grounding (default `False`) |
| `thinking` | Enable chain-of-thought reasoning (default `False`) |
| `chat_id` | Session UUID for multi-turn context |

### Tongyi Qianwen

| Option | Meaning |
| --- | --- |
| `session_id` | Continue an existing conversation session |
| `parent_msg_id` | Parent message ID for threading |

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
- HuggingFace Chat session bootstrap, conversation creation, and streaming
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
- HuggingFace Chat: `Soulter/hugging-chat-api`, `SreejanPersonal/Hugging-Chat-Reverse-Engineered-API`

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
