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

All providers use the same `LLMCookieBridge.create(name, ...)` factory. Auth
material falls into four patterns:

```python
import os
from llm_cookie_bridge import LLMCookieBridge

# 1. Cookie dict — copy values from DevTools -> Application -> Cookies
LLMCookieBridge.create("gemini", cookies={
    "__Secure-1PSID": os.environ["GEMINI_1PSID"],
    "__Secure-1PSIDTS": os.environ["GEMINI_1PSIDTS"],
})

# 2. Full cookie header — DevTools -> Network -> any request -> "Cookie" header
LLMCookieBridge.create("claude", cookie_header=os.environ["CLAUDE_COOKIE_HEADER"])

# 3. Bearer token / API key — localStorage, an Authorization header, or a
#    dashboard-issued key depending on the provider
LLMCookieBridge.create("openrouter", auth_token=os.environ["OPENROUTER_API_KEY"])

# 4. Anonymous — no auth required
LLMCookieBridge.create("duckai")
```

| `create()` name | Product | Auth | How to get credentials |
| --- | --- | --- | --- |
| `gemini` | Google Gemini | cookies | `__Secure-1PSID`, `__Secure-1PSIDTS` from gemini.google.com |
| `chatgpt` | ChatGPT | cookies / `access_token` | `__Secure-next-auth.session-token` or a web bearer token |
| `claude` | Claude | cookie_header | Header containing `sessionKey=...` from claude.ai |
| `perplexity` | Perplexity | cookies | `__Secure-next-auth.session-token` |
| `huggingface` | HuggingFace Chat | cookies | `hf-chat` from huggingface.co/chat |
| `grok` | Grok (xAI) | cookies | `sso`, `sso-rw`, `x-anonuserid`, `x-challenge`, `x-signature` from grok.com |
| `phind` | Phind | none / cookies | Anonymous works; `next-auth.session-token` unlocks all models |
| `deepseek` | DeepSeek | auth_token | `JSON.parse(localStorage.getItem("userToken")).value` at chat.deepseek.com |
| `you` | You.com | none / cookies | Anonymous for default models; cookie header for custom models |
| `pi` | Pi.ai | none / cookies | Anonymous works; cookies for account-linked sessions |
| `meta` | Meta AI | none / cookies | Anonymous in supported regions (geo-blocked elsewhere) |
| `mistral` | Mistral Le Chat | cookie_header | Full cookie header from chat.mistral.ai |
| `copilot` | Microsoft Copilot | cookie_header | Full header incl. `_U`, `MUID` from copilot.microsoft.com |
| `poe` | Poe | cookies | `p-b` + `p-lat` cookies; `formkey` optional (auto-fetched) |
| `blackbox` | Blackbox AI | auth_token | API key from the blackbox.ai dashboard |
| `characterai` | Character.AI | auth_token | `Authorization: Token <value>` header of any app request |
| `qwen` | Qwen Chat | auth_token | `localStorage.getItem("token")` at chat.qwen.ai |
| `tongyi` | Tongyi Qianwen | auth_token | `localStorage.getItem("token")` at www.qianwen.com |
| `duckai` | DuckDuckGo AI | none | Anonymous; `x-vqd-4` token fetched automatically |
| `zai` | Z.ai (GLM) | none / auth_token | Guest token fallback; account token unlocks higher limits |
| `kimi` | Kimi (Moonshot) | auth_token | Access token from a kimi.com session |
| `lmarena` | LM Arena | none | Anonymous arena chat |
| `openrouter` | OpenRouter | auth_token | API key from openrouter.ai/keys |
| `groq` | GroqCloud | auth_token | API key from console.groq.com |
| `together` | Together AI | auth_token | API key from api.together.ai settings |
| `githubmodels` | GitHub Models | auth_token | GitHub PAT with `models:read` |
| `doubao` | Doubao (ByteDance) | cookies | `sessionid` cookie from doubao.com |
| `yuanbao` | Yuanbao (Tencent) | cookies | Session cookies from yuanbao.tencent.com |
| `chatglm` | ChatGLM (Zhipu) | auth_token | Web token from chatglm.cn |
| `sparkdesk` | SparkDesk (iFlytek) | cookies | Session cookies from xinghuo.xfyun.cn |
| `hailuo` | Hailuo (MiniMax) | auth_token | Web token from hailuo.ai |
| `iask` | iAsk | none | Anonymous |
| `scira` | Scira | none | Anonymous; Vercel data-protocol stream |
| `komo` | Komo | none | Anonymous |
| `andi` | Andi | none | Anonymous |
| `felo` | Felo | none | Anonymous |
| `devv` | Devv | none | Anonymous dev-focused search |
| `venice` | Venice AI | none | Anonymous, privacy-focused |
| `deepai` | DeepAI | none | Anonymous |
| `aistudio` | Google AI Studio | cookies | Google account cookies incl. `__Secure-1PSID` |
| `notebooklm` | NotebookLM | cookies | Google account cookies |
| `cohere` | Cohere | auth_token | API key from dashboard.cohere.com (v2 chat API) |
| `lumo` | Proton Lumo | cookies | Proton session cookies |
| `v0` | v0 (Vercel) | cookies | Session cookies from v0.dev |
| `bolt` | Bolt.new | none | Anonymous |
| `lovable` | Lovable | cookies | Session cookies from lovable.dev |
| `websim` | Websim | auth_token | API key from websim.ai |
| `monica` | Monica | cookies | Session cookies from monica.im |
| `sider` | Sider | cookies | Session cookies from sider.ai |
| `merlin` | Merlin | cookies | Session cookies from getmerlin.in |
| `popai` | PopAI | cookies | Session cookies from popai.pro |
| `genspark` | Genspark | cookies | Session cookies from genspark.ai |
| `skywork` | Skywork | cookies | Session cookies from skywork.ai |
| `sensechat` | SenseChat | auth_token | Web token from chat.sensetime.com |
| `baichuan` | Baichuan | cookies | Session cookies from baichuan-ai.com |
| `wrtn` | Wrtn | cookies | Session cookies from wrtn.ai |
| `coze` | Coze | cookies | Session cookies from coze.com; pass `bot_id` to pick a bot |
| `kagi` | Kagi Assistant | cookies | Paid Kagi account cookies |
| `cody` | Sourcegraph Cody | auth_token | Sourcegraph access token |
| `ai360` | 360 Zhinao | cookies | Session cookies from bot.n.cn |
| `abacus` | Abacus ChatLLM | cookies | Session cookies from apps.abacus.ai |

Notable provider options: `poe` accepts `bot=`, `coze` accepts `bot_id=`,
`meta` accepts `birthday=` for anonymous ToS, and most providers accept
`model=` plus a conversation id (`conversation_id`/`chat_id`) for
continuity. See [Provider-specific chat options](#provider-specific-chat-options).


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
