# Provider verification

**2026-11-26 (Asia/Seoul)** · Baseline `5955db38884f49ab41c92d4150940b8a357894ed`.

**Result:** Zero providers met the live acceptance criteria. Every provider
below is disabled. No provider account was created. Authenticated chat,
incremental streaming, follow-up turns, and session recovery were untested
for every provider. The observations below concern the public site and
registration entry point.

The managed browser MCP failed during initialization with
`the gaas-browser node_repl sandbox cannot be disabled`. Playwright MCP
0.0.86 with isolated Chromium reached the public URLs below. Where an
entry point was opened, the observation is limited to its visible controls.
HTTP status codes are what Chromium received, including any intermediary
response. Retries often returned 503 as outbound HTTPS began returning
upstream connection failures across unrelated hosts.

The disposable-email MCP exposed its mailbox tools, but `create_one_account`
returned no usable credentials. A diagnostic retry observed an HTTP 503
from the environment's network path on `GET https://api.mail.tm/domains`;
the MCP issued no mailbox creation request on that retry. No disposable
address was submitted on a provider website. Provider acceptance of
disposable email remains unknown.

| Disabled provider ID | Public browser entry | Observation and blocker |
| --- | --- | --- |
| `abacus` | [apps.abacus.ai](https://apps.abacus.ai/) | HTTP 200 → HTTP 503. Sign-in page offered email, Google, Apple, and Microsoft. |
| `ai360` | [bot.n.cn](https://bot.n.cn/) | Timeout 12000ms exceeded → HTTP 503. No registration screen observed. |
| `aistudio` | [aistudio.google.com](https://aistudio.google.com/) | HTTP 200 → HTTP 503. Welcome page offered “Sign up and get started.” |
| `andi` | [andisearch.com](https://andisearch.com/) | HTTP 200 → HTTP 503. Public search page loaded. No signup control surfaced. |
| `baichuan` | [www.baichuan-ai.com](https://www.baichuan-ai.com/) | HTTP 200 → HTTP 503. Landing page showed 登录 (log in). |
| `blackbox` | [www.blackbox.ai](https://www.blackbox.ai/) | HTTP 200 → HTTP 503. Public site showed login controls. |
| `bolt` | [bolt.new](https://bolt.new/) | HTTP 200 → HTTP 503. Builder page showed “Sign in” and “Get Started.” |
| `characterai` | [character.ai](https://character.ai/) | HTTP 200. “Sign Up to Chat” opened a dialog offering email, Google, and Apple. |
| `chatglm` | [chatglm.cn](https://chatglm.cn/) | HTTP 200 → HTTP 503. AgentMore landing page showed 登录 (log in). |
| `chatgpt` | [chatgpt.com](https://chatgpt.com/) | HTTP 200 → HTTP 503. Landing page showed “Sign up for free” and “Log in.” |
| `claude` | [claude.ai](https://claude.ai/) | HTTP 200 → HTTP 503. Account page offered email, Google, and Apple. |
| `cody` | [sourcegraph.com](https://sourcegraph.com/) | HTTP 200 → HTTP 503. Sourcegraph returned a product landing page. No Cody signup control surfaced. |
| `cohere` | [dashboard.cohere.com](https://dashboard.cohere.com/) | HTTP 200 → HTTP 503. Dashboard sign-in page offered signup, email login, Google, and GitHub. |
| `copilot` | [copilot.microsoft.com](https://copilot.microsoft.com/) | HTTP 200 → HTTP 503. Redirected to copilot.com. Product landing page offered Microsoft sign-in. |
| `coze` | [www.coze.com](https://www.coze.com/) | HTTP 200 → HTTP 503. Public landing page loaded. No signup control surfaced. |
| `deepai` | [deepai.org](https://deepai.org/) | HTTP 200 → HTTP 503. Public page showed “Login.” |
| `deepseek` | [chat.deepseek.com](https://chat.deepseek.com/) | HTTP 200 → HTTP 503. “Sign up” opened the registration UI with an email entry point. |
| `devv` | [devv.ai](https://devv.ai/) | HTTP 200 → HTTP 503. Coding product page showed “Sign in” and “Sign up.” |
| `doubao` | [www.doubao.com](https://www.doubao.com/) | Navigation failed → HTTP 503. No registration screen observed. |
| `duckai` | [duckduckgo.com/aichat](https://duckduckgo.com/aichat) | HTTP 200 → HTTP 503. Redirected to duck.ai. Public chat UI returned without a signup control. |
| `felo` | [felo.ai](https://felo.ai/) | HTTP 200 → HTTP 503. Landing page showed “Login.” |
| `gemini` | [gemini.google.com](https://gemini.google.com/) | HTTP 200 → HTTP 503. Gemini landing page loaded. No signup control surfaced. |
| `genspark` | [www.genspark.ai](https://www.genspark.ai/) | HTTP 200 → HTTP 503. Product page loaded. No signup control surfaced. |
| `githubmodels` | [github.com/marketplace/models](https://github.com/marketplace/models) | HTTP 404 → HTTP 503. Marketplace route returned a GitHub page titled “Page not found.” |
| `grok` | [grok.com](https://grok.com/) | HTTP 200 → HTTP 503. Public page showed “Sign in” and “Sign up.” |
| `groq` | [console.groq.com](https://console.groq.com/) | HTTP 200 → HTTP 503. GroqCloud opened with a “Log In” control. |
| `hailuo` | [www.hailuo.ai](https://www.hailuo.ai/) | HTTP 200 → HTTP 503. Redirected to agent.minimax.cn and opened the MiniMax Code landing page. |
| `huggingface` | [huggingface.co/chat](https://huggingface.co/chat) | HTTP 200 → HTTP 503. HuggingChat page loaded. No signup control surfaced. |
| `iask` | [iask.ai](https://iask.ai/) | HTTP 200 → HTTP 503. Search page showed “Log In” and “Sign Up.” |
| `kagi` | [kagi.com](https://kagi.com/) | HTTP 200 → HTTP 503. Landing page showed “Sign up for free” and “Sign in.” |
| `kimi` | [www.kimi.com](https://www.kimi.com/) | HTTP 200 → HTTP 503. Product landing page loaded. No signup control surfaced. |
| `komo` | [komo.ai](https://komo.ai/) | HTTP 200 → HTTP 503. Search page showed “Sign in.” |
| `lmarena` | [lmarena.ai](https://lmarena.ai/) | HTTP 200 → HTTP 503. Redirected to arena.ai. Landing page showed “Log in” and “Sign up for free.” |
| `lovable` | [lovable.dev](https://lovable.dev/) | HTTP 200 → HTTP 503. Builder page showed “Log in” and “Get started.” |
| `lumo` | [lumo.proton.me](https://lumo.proton.me/) | HTTP 200 → HTTP 503. Public assistant page loaded. No signup control surfaced. |
| `merlin` | [www.getmerlin.in](https://www.getmerlin.in/) | HTTP 200 → HTTP 503. Marketing page loaded. No signup control surfaced. |
| `meta` | [www.meta.ai](https://www.meta.ai/) | HTTP 403 → HTTP 503. The HTTP 403 page showed a “Log in” control. |
| `mistral` | [chat.mistral.ai](https://chat.mistral.ai/) | HTTP 200 → HTTP 503. The page identified itself as Vibe Work and showed “Sign up” and “Sign in.” |
| `monica` | [monica.im](https://monica.im/) | HTTP 200 → HTTP 503. Landing page showed “Log In.” |
| `notebooklm` | [notebooklm.google.com](https://notebooklm.google.com/) | HTTP 200 → HTTP 503. Redirected to notebook.google.com. Gemini Notebook page offered sign-in. |
| `openrouter` | [openrouter.ai/chat](https://openrouter.ai/chat) | HTTP 200 → HTTP 503. Public chat playground offered “Sign up” and “Sign in.” |
| `perplexity` | [www.perplexity.ai](https://www.perplexity.ai/) | HTTP 200 → HTTP 503. Public page loaded. No signup control surfaced. |
| `phind` | [www.phind.com](https://www.phind.com/) | HTTP 404 → HTTP 503. Page displayed “404: NOT_FOUND.” |
| `pi` | [pi.ai](https://pi.ai/) | HTTP 200 → HTTP 503. Public page showed “Log in.” |
| `poe` | [poe.com](https://poe.com/) | HTTP 200 → HTTP 503. Account UI offered email, Google, and Apple. |
| `popai` | [popai.pro](https://popai.pro/) | Timeout 12000ms exceeded → HTTP 503. Redirected to www.popai.pro. The page title appeared before navigation timed out. |
| `qwen` | [chat.qwen.ai](https://chat.qwen.ai/) | HTTP 200 → HTTP 503. Chat landing page showed “Log in” and “Sign up.” |
| `scira` | [scira.ai](https://scira.ai/) | HTTP 200 → HTTP 503. Public page showed “Sign in.” |
| `sensechat` | [chat.sensetime.com](https://chat.sensetime.com/) | Timeout 12000ms exceeded → HTTP 503. No registration screen observed. |
| `sider` | [sider.ai](https://sider.ai/) | Timeout 12000ms exceeded → HTTP 503. No registration screen observed. |
| `skywork` | [skywork.ai](https://skywork.ai/) | HTTP 503. No registration screen observed. |
| `sparkdesk` | [xinghuo.xfyun.cn](https://xinghuo.xfyun.cn/) | HTTP 503. No registration screen observed. |
| `together` | [api.together.ai](https://api.together.ai/) | Navigation failed → HTTP 503. No registration screen observed. |
| `tongyi` | [www.qianwen.com](https://www.qianwen.com/) | HTTP 200 → HTTP 503. Qianwen page loaded. No signup control surfaced. |
| `v0` | [v0.dev](https://v0.dev/) | HTTP 200 → HTTP 503. Redirected to v0.app. Builder page showed “Log In” and “Sign Up.” |
| `venice` | [venice.ai](https://venice.ai/) | HTTP 503. No registration screen observed. |
| `websim` | [websim.ai](https://websim.ai/) | HTTP 503. No registration screen observed. |
| `wrtn` | [wrtn.ai](https://wrtn.ai/) | HTTP 402 → HTTP 503. No registration screen observed. |
| `you` | [you.com](https://you.com/) | HTTP 503. No registration screen observed. |
| `yuanbao` | [yuanbao.tencent.com](https://yuanbao.tencent.com/) | Timeout 12000ms exceeded → HTTP 503. The Yuanbao page title appeared before navigation timed out. |
| `zai` | [chat.z.ai](https://chat.z.ai/) | HTTP 503. No registration screen observed. |

## Repository audit

The baseline inventory covered 103 tracked files, including all 61 provider
adapters and all 23 test modules. Provider modules used a mix of public API
keys, browser cookies or bearer tokens, and anonymous calls. Several paths
bootstrapped a session or conversation ID before streaming. Their request
shapes, credential handling, and parsers had no live evidence from this run.

| Baseline files | Disposition |
| --- | --- |
| `src/llm_cookie_bridge/providers/*.py` | Removed all adapters, their exports, the base provider, and the shared parser. Each adapter's provider ID appears above. |
| `src/llm_cookie_bridge/{__init__,client,exceptions,sse,types,utils}.py` | Replaced the transport, factory, state, error, and parsing surface with the availability API. |
| `tests/*.py` | The baseline suite passed 191 tests on Python 3.12. It used mocked HTTP responses and local assertions. The replacement suite tests provider rejection. |
| `README.md`, `assets/*.svg` | Replaced the compatibility and setup claims with current availability. Removed the three decorative logo files. |
| `pyproject.toml`, `.gitignore`, `LICENSE` | Reworked package metadata and development dependencies. Retained the ignore rules and MIT license. |
| `.github/workflows/{ci,publish}.yml`, `renovate.json` | Rebuilt CI around regression, lint, type, security, and build checks. Removed the PyPI publication workflow and the inherited automerge preset. |

The old base client allowed overriding the credential destination and
included remote response bodies in exceptions. Its 401/403 retry path could
replay a chat request. The replacement has no network client or runtime
dependencies and accepts no credentials.

A provider can be re-enabled after an authorized signup and a live run of the
actual integration. Record observed authentication, a completed chat, multiple
nonempty stream updates before completion, a follow-up that recalls a unique
marker from the first turn, and recovery from an expired or invalid session.
Keep credentials, verification links, and conversation identifiers out of the
record.
