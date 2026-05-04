# CodexRosetta

**Responses API <-> Chat Completions API 代理服务器**

CodexRosetta 是一个轻量级代理，在 OpenAI 的 [Responses API](https://platform.openai.com/docs/api-reference/responses) 和广泛兼容的 [Chat Completions API](https://platform.openai.com/docs/api-reference/chat) 之间进行双向转换。它让任何兼容 Chat Completions 的后端都能驱动需要 Responses API 格式的工具和客户端——双方都无需修改代码。

## 为什么需要 CodexRosetta？

OpenAI 推出了 Responses API 作为 Chat Completions 的继任者，但大多数第三方 LLM 服务商和自建后端（vLLM、Ollama、LiteLLM 等）仅支持 Chat Completions。CodexRosetta 填补了这个空白：

- **用任何 LLM 驱动 Codex / 类 ChatGPT 工具** — 将客户端指向 CodexRosetta，它会实时将 Responses API 请求转换为 Chat Completions 格式
- **零客户端改动** — 你的工具继续发送 Responses API 请求，CodexRosetta 透明地处理转换
- **流式支持** — 完整的 SSE 流式转换，包括工具调用和多轮联网搜索
- **内置联网搜索** — 通过 Tavily、SearXNG、Brave 或 DuckDuckGo 模拟 Responses API 的 `web_search` 工具
- **多 Key 管理** — 通过 Web 界面或 REST API 添加、轮换和切换 API Key

## 快速开始

### Docker（推荐）

```bash
docker run -d \
  --name codex-rosetta \
  -p 33131:33131 \
  jlny/codex-rosetta:latest
```

然后将客户端指向 `http://localhost:33131/v1/responses`。

### Docker Compose

包含 Redis 用于会话状态持久化：

```bash
git clone https://github.com/JiuliNuoyi/CodexRosetta.git
cd CodexRosetta
cp .env.example .env
# 编辑 .env，配置上游服务商
docker compose up -d
```

### pip 安装

```bash
pip install codex-rosetta
codex-rosetta
```

### 从源码安装

```bash
git clone https://github.com/JiuliNuoyi/CodexRosetta.git
cd CodexRosetta
pip install .
cp .env.example .env
# 编辑 .env，配置上游服务商
codex-rosetta
```

## 工作原理

```
┌──────────┐    Responses API     ┌────────────────┐    Chat Completions API    ┌──────────┐
│  客户端   │ ──────────────────▶ │  CodexRosetta   │ ─────────────────────────▶ │ 上游服务  │
│ (Codex,   │ ◀────────────────── │                 │ ◀─────────────────────────  │  提供商  │
│  等)      │    Responses API    │  ┌───────────┐  │    Chat Completions API    │          │
└──────────┘    (转换回)          │  │  转换管线  │  │    (原始响应)              └──────────┘
                                   │  ├───────────┤  │
                                   │  │• 输入转换  │  │
                                   │  │• 工具转换  │  │
                                   │  │• 请求转换  ���  │
                                   │  │• 流式转换  │  │
                                   │  │• 响应转换  │  │
                                   │  └───────────┘  │
                                   └────────────────┘
```

### 转换管线

当 Responses API 请求到达时，CodexRosetta 通过多阶段管线处理：

1. **输入转换器（InputTransformer）** — 将 Responses API 的 `input` 数组转换为扁平的 Chat Completions `messages` 数组。`instructions` 变为 system 消息；`developer` 角色映射为 `system`；`function_call` / `function_call_output` 分别映射为 assistant 的 tool_calls 和 tool 消息；`custom_tool_call` / `custom_tool_call_output` 做同样映射。

2. **工具转换器（ToolTransformer）** — 在两种格式之间转换工具定义。Function 工具从扁平结构（`name`、`parameters`、`description` 在顶层）重组为嵌套结构（包裹在 `function` 键内）。Responses API 内置工具类型（`web_search`、`file_search`、`computer_use_preview`、`code_interpreter`、`image_generation`）均为 OpenAI 云端执行的工具，Chat Completions API 中没有对应物。CodexRosetta 将它们模拟为 `__rosetta_` 前缀的普通 function 工具，其中 `web_search` 已通过第三方搜索服务实现本地替代，其余工具暂时不可用，需等待上游模型商提供支持或后续更新。

3. **请求转换器（RequestConverter）** — 编排上述转换器，并映射参数：`max_output_tokens` → `max_completion_tokens`、`text.format` → `response_format`、`reasoning.effort` → `reasoning_effort`、`text.verbosity` 追加提示到 system 消息。此外处理客户端传来的 `truncation: auto`——这是 Responses API 的参数，表示上下文溢出时自动截断，由客户端（如 Codex）发出。由于 Chat Completions API 没有此参数，CodexRosetta 在代理层接管了这个逻辑：当上游返回上下文长度错误时，自动裁剪较早的消息并重试（最多 3 次）。还会清理畸形 JSON 工具调用参数。

4. **上游客户端（UpstreamClient）** — 通过 `httpx` 将转换后的 Chat Completions 请求发送到配置的上游服务商，支持可配置超时（默认：连接 10s，读取 300s 以应对长流式响应）。

5. **响应转换器（ResponseConverter）** — 将上游 Chat Completions 响应转换回 Responses API 格式。Assistant 消息变为 `message` 输出项；tool calls 变为 `function_call` 输出项；`__rosetta_` 前缀的函数调用反向映射回其原生内置工具类型（如 `web_search_call` 等）。转换 usage 字段（`prompt_tokens` → `input_tokens` 等）。

6. **流式转换器（StreamConverter）** — 一个状态机，实时处理 Chat Completions SSE 数据块，发出 Responses API SSE 事件（`response.created`、`response.output_item.added`、`response.content_part.delta`、`response.output_item.done`、`response.completed` 等）。跟踪每个输出项的状态（文本累积、参数累积、reasoning 内容等）。

### 会话状态

CodexRosetta 支持 Responses API 的 `previous_response_id` 和 `conversation` 模式：

- **内存存储**（默认）— 使用 TTL 驱逐策略存储会话历史，适合单实例部署
- **Redis 存储** — 跨重启持久化会话，通过 `REDIS_URL` 配置

会话存储会将 Responses API 的 output items（message、function_call 等）重建为 Chat Completions 格式的 messages，以便作为历史上下文拼接到下一轮请求中。

### 联网搜索

当 `WEB_SEARCH_ENABLED=true` 时，CodexRosetta 拦截 `__rosetta_web_search` 函数调用，查询配置的搜索服务商，并将搜索结果注入到对话中作为 tool 消息返回，然后继续请求上游模型生成回答——提供类似 OpenAI 原生联网搜索的体验。

搜索结果以模拟流式方式输出（逐字符发送），使客户端能渐进式显示搜索结果。

### 多轮搜索

当模型在同一个响应中多次调用 `web_search` 时，CodexRosetta 自动串联搜索轮次：拦截搜索调用 → 查询搜索 API → 将结果注入 → 重新请求上游 → 继续流式输出，所有这些都在单个 SSE 连接内完成，最多循环 `WEB_SEARCH_MAX_ROUNDS` 轮。

### 内置工具模拟

Responses API 的部分内置工具为 OpenAI 云端执行，Chat Completions API 没有对应物。CodexRosetta 将它们模拟为 `__rosetta_` 前缀的普通 function 工具：

- **web_search** — ✅ 已通过第三方搜索服务（Tavily、SearXNG、Brave、DuckDuckGo）实现本地替代，可正常使用
- **file_search** — ❌ 暂时不可用，需等待上游模型商提供支持或后续更新
- **computer_use_preview** — ❌ 暂时不可用，需等待上游模型商提供支持或后续更新
- **code_interpreter** — ❌ 暂时不可用，需等待上游模型商提供支持或后续更新
- **image_generation** — ❌ 暂时不可用，需等待上游模型商提供支持或后续更新

## 项目架构

```
codex_rosetta/
├── main.py                 # FastAPI 应用工厂、中间件注册、启动逻辑
├── config.py               # 配置管理（pydantic-settings，.env 文件）
├── api/
│   ├── router.py           # POST /v1/responses — 主代理端点
│   ├── keys_router.py      # /v1/keys — Key 管理 REST API
│   ├── settings_router.py  # /v1/settings — 运行时设置 REST API
│   ├── web_router.py       # /app — 前端 SPA 静态文件服务
│   └── dependencies.py     # FastAPI 依赖注入（upstream client、conversation store）
├── converters/
│   ├── request_converter.py   # 请求转换编排器
│   ├── response_converter.py  # 非流式响应转换
│   ├── stream_converter.py    # SSE 流式状态机
│   ├── input_transformer.py   # input 数组 → messages 数组
│   ├── tool_transformer.py    # 工具定义转换（含内置工具模拟）
│   └── content_transformer.py # 内容部件转换（input_text、input_image 等）
├── builtin_tools/
│   ├── registry.py         # 内置工具模拟器注册表
│   ├── web_search.py       # 联网搜索模拟器（已实现本地替代）
│   ├── file_search.py      # 文件搜索模拟器（暂不可用）
│   ├── computer_use.py     # 电脑操控模拟器（暂不可用）
│   ├── code_interpreter.py # 代码解释器模拟器（暂不可用）
│   └── image_generation.py # 图像生成模拟器（暂不可用）
├── upstream/
│   ├── client.py           # 异步 HTTP 客户端（httpx）
│   └── provider_adapters.py # 服务商适配器（OpenAI 直通、Anthropic/Google 参数清理）
├── state/
│   ├── conversation_store.py  # 内存 & Redis 会话存储
│   └── stream_state.py        # 流式转换输出项状态追踪
├── search/
│   ├── base.py             # SearchProvider 抽象基类
│   ├── tavily_provider.py  # Tavily 搜索
│   ├── searxng_provider.py # SearXNG 搜索
│   ├── brave_provider.py   # Brave 搜索
│   ├── duckduckgo_provider.py # DuckDuckGo 搜索（支持直连和远程 API）
│   ├── http_provider.py    # 通用 HTTP 搜索
│   └── formatter.py        # 搜索结果格式化
├── models/
│   └── common.py           # ConversionContext、工具类型常量、__rosetta_ 前缀
├── keys/
│   └── manager.py          # 多 Key 管理（增删改查、激活切换、JSON 持久化）
├── audit/
│   ├── middleware.py        # 审计中间件（捕获原始请求和最终响应）
│   └── logger.py           # 审计日志写入器
└── utils/
    ├── id_generation.py    # resp_、msg_、fc_ 等 ID 生成
    ├── logging.py          # Structlog 配置
    └── sse.py              # SSE 事件格式化/解析
```

## 支持的服务商

| 服务商 | `UPSTREAM_PROVIDER` | 说明 |
|---|---|---|
| **OpenAI** | `openai` | 默认，完整支持，请求直通 |
| **其他** | `other` | 任何 OpenAI 兼容 API（vLLM、Ollama、LiteLLM 等），回退为 OpenAI 直通适配器 |

## 配置

所有设置均可通过环境变量或 `.env` 文件配置：

### 核心设置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `UPSTREAM_BASE_URL` | `https://api.openai.com/v1` | 上游 Chat Completions API 地址 |
| `UPSTREAM_API_KEY` | *（必填）* | 上游服务商的 API Key |
| `UPSTREAM_PROVIDER` | `openai` | 服务商：`openai`、`anthropic`、`google`、`other` |
| `HOST` | `0.0.0.0` | 服务监听地址 |
| `PORT` | `33131` | 服务监听端口 |

### 会话存储

| 变量 | 默认值 | 说明 |
|---|---|---|
| `REDIS_URL` | *（禁用）* | Redis 地址，用于会话持久化（如 `redis://localhost:6379/0`） |
| `MAX_CONVERSATION_HISTORY` | `100` | 每个会话保留的最大消息数 |
| `CONVERSATION_TTL_SECONDS` | `3600` | 存储会话的生存时间（秒） |

### 联网搜索

| 变量 | 默认值 | 说明 |
|---|---|---|
| `WEB_SEARCH_ENABLED` | `false` | 启用联网搜索工具 |
| `WEB_SEARCH_PROVIDER` | `custom` | 搜索服务商：`tavily`、`searxng`、`brave`、`duckduckgo`、`custom` |
| `WEB_SEARCH_BASE_URL` | *（空）* | 搜索 API 地址（`searxng`、`custom` 必填；`duckduckgo` 可选用于远程 API） |
| `WEB_SEARCH_API_KEY` | *（空）* | 搜索 API Key（`tavily`、`brave` 必填；`searxng`、`custom`、`duckduckgo` 可选） |
| `WEB_SEARCH_MAX_RESULTS` | `5` | 每次查询最大搜索结果数 |
| `WEB_SEARCH_MAX_ROUNDS` | `3` | 每个响应最大搜索轮次 |
| `WEB_SEARCH_SIMULATED_STREAMING_ENABLED` | `true` | 逐字符流式输出搜索结果 |
| `WEB_SEARCH_SIMULATED_STREAM_DELAY_MS` | `25` | 模拟流式输出每字符延迟（毫秒） |
| `WEB_SEARCH_SIMULATED_STREAM_MAX_CHARS` | `32` | 模拟流式输出每块最大字符数 |

### 日志与审计

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_UPSTREAM_REQUESTS` | `false` | 记录完整的上游请求体 |
| `LOG_UPSTREAM_RESPONSES` | `false` | 记录完整的上游响应体 |
| `DEBUG_LOG_FILE` | *（禁用）* | 将 JSON 调试日志写入文件 |
| `AUDIT_ENABLED` | `false` | 启用请求审计日志 |
| `AUDIT_DIR` | `./audit` | 审计日志文件目录 |

### 超时设置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `UPSTREAM_TIMEOUT_CONNECT` | `10` | 连接超时（秒） |
| `UPSTREAM_TIMEOUT_READ` | `300` | 读取超时（秒）— 流式响应需设高 |

### Key 管理

| 变量 | 默认值 | 说明 |
|---|---|---|
| `KEYS_FILE` | `./keys.json` | Key 存储文件路径 |

完整配置参考：[.env.example](.env.example)

## Web 管理界面

CodexRosetta 内置管理界面，访问 `http://localhost:33131/app`：

- **Dashboard** — API Key 管理（添加、编辑、删除、切换激活），显示 Key 统计
- **Playground** — 内置聊天测试界面，可直接测试代理转换是否正常工作
- **Settings** — 运行时设置编辑（日志级别、联网搜索配置等），无需重启

Key 也可以通过 `/v1/keys` REST API 管理（支持 GET 列表、POST 添加、PUT 修改/激活、DELETE 删除）。

## 注意事项

- **API Key 安全** — 上游 API Key 仅发送给配置的上游服务商。CodexRosetta 不会将其记录日志或传输到其他地方。`.env` 文件和 `keys.json` 应妥善保管并排除在版本控制之外。
- **流式超时** — 默认读取超时为 300 秒。如果使用长时间运行的模型，可能需要增加 `UPSTREAM_TIMEOUT_READ`。
- **上下文溢出自动重试** — `truncation=auto` 是客户端（如 Codex）在 Responses API 请求中传来的参数。由于 Chat Completions API 不支持此参数，CodexRosetta 在代理层接管了这个逻辑：当上游返回上下文长度错误时，自动裁剪较早的非系统消息（每次裁剪 1/4）并重试，最多 3 次。若客户端未传此参数，则超上下文直接报错。
- **内置工具模拟范围** — Responses API 的内置工具均为 OpenAI 云端执行。目前仅 `web_search` 已通过第三方搜索服务实现本地替代，其余工具（`file_search`、`computer_use_preview`、`code_interpreter`、`image_generation`）暂时不可用，需等待上游模型商提供支持或后续更新。
- **畸形 JSON 修复** — 某些模型（如 GLM）可能生成格式错误的工具调用参数 JSON。CodexRosetta 会自动尝试修复截断的 JSON（闭合未关闭的引号和大括号），无法修复时回退为 `{}`，防止上游返回 400 错误。
- **生产环境请使用 Redis** — 默认的内存会话存储在服务重启后会丢失状态。生产环境请通过 `REDIS_URL` 配置 Redis。
- **反向代理** — 如果部署在反向代理（nginx、Caddy）后面，请确保 SSE 连接不被缓冲。nginx 需添加 `proxy_buffering off;`。

## 技术栈

**后端：** Python 3.11+ · FastAPI · Uvicorn · httpx · Pydantic · structlog · Redis（可选）

**前端：** React 19 · TypeScript · Vite · Tailwind CSS 4 · Framer Motion · Lucide

## 后续规划

- **Anthropic 接口接入** — 目前 Anthropic 适配器仅做了参数兼容处理，后续将支持 Anthropic 原生 Messages API 的直接接入，无需依赖 Chat Completions 兼容端点
- **修复 Codex Desktop 流式输出** — 已知 Codex Desktop 客户端不支持流式输出，后续将修复此兼容性问题
- **完善内置工具支持** — 逐步实现对 `file_search`、`computer_use_preview`、`code_interpreter`、`image_generation` 等 OpenAI 云端工具的本地替代

## 开源协议

[MIT](LICENSE)



