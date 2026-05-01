# CodexRosetta — Responses API 独有参数处理说明

## Codex 会发送、需要处理的参数

### 1. `include`
- **作用**: 请求响应中包含额外数据，Codex 会发送 `include: ["reasoning.encrypted_content"]`
- **影响**: 多轮推理对话需要加密推理上下文，忽略后推理质量下降
- **处理方案**: 记录到 ConversionContext，响应转换时对不支持的字段返回空值占位（如 `reasoning.encrypted_content` 返回 `null`）
- **当前状态**: 已实现 — 记录到 ConversionContext，响应转换时注入 null 占位符

### 2. `text.verbosity`
- **作用**: 控制回复长度，`"low"`(简洁) / `"medium"`(默认) / `"high"`(详细)
- **影响**: 忽略后第三方模型可能比预期更冗长或过于简短
- **处理方案**: 在请求转换时，往 system message 追加提示语：
  - `verbosity: "low"` → 追加 `"Be concise and brief in your responses."`
  - `verbosity: "high"` → 追加 `"Provide detailed and thorough responses."`
  - `verbosity: "medium"` → 不追加
- **当前状态**: 已实现 — 追加提示语到 system message

### 3. `prompt_cache_key`
- **作用**: 缓存优化键，替代 `user` 字段用于缓存命中
- **影响**: 忽略只影响缓存命中率，功能不受影响
- **处理方案**: 直接透传（Chat Completions 也支持此字段）
- **当前状态**: 已在透传列表中

---

## Codex 不会发送、可安全忽略的参数

### 4. `max_tool_calls`
- **作用**: 限制内置工具（web_search、file_search、code_interpreter、computer_use）的调用总次数，不影响用户定义的 function 工具
- **忽略原因**: 代理到第三方模型时内置工具已模拟为 function，第三方模型有自己的工具调用频率管理
- **处理方案**: 静默忽略
- **当前状态**: 已实现 — 记录到 ConversionContext，响应转换时截断超限工具调用

### 5. `truncation`
- **作用**: `"auto"` 时服务端自动裁剪超出上下文的历史消息；`"disabled"`（默认）时超长直接报 400 错误
- **忽略原因**: Codex 自己做客户端上下文管理（compaction），不发送此参数
- **处理方案**: 静默忽略。如需通用代理支持，可自行实现上下文裁剪逻辑
- **当前状态**: 已实现 — truncation="auto" 时捕获 400 context_length 错误，自动裁剪 25% 非系统消息并重试
- **作用**: 异步模式，API 立即返回 `queued`/`in_progress` 状态，通过轮询或 webhook 获取结果
- **忽略原因**: Codex 始终使用流式模式（`stream: true`），不发送此参数
- **处理方案**: 静默忽略，请求按同步/流式处理
- **当前状态**: 未实现

### 7. `conversation`
- **作用**: `previous_response_id` 的替代方案，通过 `conversation: { id: "conv_xxx" }` 让服务端管理会话历史，与 `previous_response_id` 互斥
- **忽略原因**: Codex 使用 `previous_response_id` 管理多轮对话，不使用此参数
- **处理方案**: 如需支持，需从 conversation store 读取历史并组装 messages
- **当前状态**: 已实现 — conversation 参数从 store 读取历史消息，支持 conversation_id 存储和查找

### 8. `prompt`
- **作用**: 引用 OpenAI Prompt 库中存储的模板（通过 ID + 版本 + 变量），自动展开为 instructions + input
- **忽略原因**: Codex 不使用，这是 OpenAI 平台专属功能，第三方模型无对应概念
- **处理方案**: 静默忽略
- **当前状态**: 未实现

### 9. `prompt_cache_retention`
- **作用**: 延长 prompt 缓存保留时间，`"in_memory"`（默认 5 分钟）或 `"24h"`
- **忽略原因**: Codex 不发送，纯 OpenAI 服务端缓存策略优化
- **处理方案**: 静默忽略
- **当前状态**: 未实现

### 10. `context_management`
- **作用**: 服务端上下文压缩配置，如 `[{ type: "compaction", compact_threshold: 50000 }]`，超过阈值自动压缩历史
- **忽略原因**: Codex 自己做客户端压缩（通过 `/responses/compact` 端点），不发送此参数
- **处理方案**: 静默忽略。如需通用代理支持，可在代理层自行实现上下文压缩
- **当前状态**: 未实现

---

## 实现优先级

| 优先级 | 参数 | 理由 |
|--------|------|------|
| ~~P0~~ | ~~`include`~~ | ✅ 已实现 |
| ~~P1~~ | ~~`text.verbosity`~~ | ✅ 已实现 |
| ~~P2~~ | ~~`conversation`~~ | ✅ 已实现 |
| ~~P3~~ | ~~`truncation`~~ | ✅ 已实现 |
| ~~P3~~ | ~~`max_tool_calls`~~ | ✅ 已实现 |
| — | `background` | 可永久忽略，Codex 不使用 |
| — | `prompt` | 可永久忽略，Codex 不使用 |
| — | `prompt_cache_retention` | 可永久忽略，Codex 不使用 |
| — | `context_management` | 可永久忽略，Codex 不使用 |
