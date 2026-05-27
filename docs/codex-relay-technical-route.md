# Codex 中转站技术路线

## 目标

搭建一个面向 Codex CLI / Codex App / Codex Desktop 的专用中转站，而不是普通 OpenAI 兼容代理。

Codex 生态的关键点是：新版 Codex 主要走 OpenAI Responses API，也就是 `/v1/responses`。只支持 `/v1/chat/completions` 的 one-api/new-api 类网关，可能能服务普通聊天客户端，但很容易在 Codex 场景里不稳定。

本路线优先解决这些问题：

- 支持 Codex 的 `/v1/responses` 请求。
- 支持 ChatGPT 登录态和第三方 Provider 解耦。
- 支持固定 Provider 名，避免移动端离线和历史会话丢失。
- 支持多上游、多 Key、限流、计费、用量统计。
- 保留后续扩展到 Codex App 增强、会话同步、协议转换的空间。

## 调研结论

推荐路线：

```text
Codex CLI / Codex App / Codex Desktop
        |
        | /v1/responses
        v
固定 Provider 名，例如 CodexPlusPlus 或 LocalCodexRelay
        |
        v
本地/自建 Codex Relay 网关
        |
        +--> OpenAI Responses API 上游
        +--> 第三方 Codex 中转上游
        +--> sub2api 账号池/订阅池
        +--> 其他兼容 Responses API 的 Provider
```

核心策略：

1. Codex 客户端永远只看到一个固定 Provider。
2. 真实上游切换、故障转移、计费和账号调度放在后端网关处理。
3. 如果使用 Codex App，可以参考 Codex++ 的中转注入方式保留 ChatGPT 登录态。
4. 如果切换 Provider 后历史会话不可见，参考 codex-provider-sync 的 metadata 同步思路。

## 候选技术

### 1. sub2api：平台底座

项目地址：https://github.com/Wei-Shaw/sub2api

定位：完整 API 网关平台。

适合用来做：

- 多账号管理。
- API Key 分发。
- 用户额度和计费。
- 账号池调度。
- 并发限制和速率限制。
- 管理后台。
- 订阅额度分发。

优点：

- 功能完整，接近商业化中转站底座。
- 社区活跃度高。
- 已经面向 Claude Code、Codex、Gemini 等编程 Agent 场景。

注意：

- 体量较大，二次开发前需要先明确数据模型和路由逻辑。
- 如果只想做最小 MVP，会显得重。

### 2. Codex++：Codex App 中转注入参考

项目地址：https://github.com/BigPizzaV3/CodexPlusPlus

定位：Codex App 外部增强启动器和管理工具。

最值得参考的是它的“中转注入”思路：

```toml
model_provider = "CodexPlusPlus"

[model_providers.CodexPlusPlus]
name = "CodexPlusPlus"
wire_api = "responses"
requires_openai_auth = true
base_url = "https://example.com/v1"
experimental_bearer_token = "sk-..."
```

适合参考：

- 保留 ChatGPT 登录态。
- 将 Model 层请求切到第三方 Responses API。
- 多个中转配置管理。
- Codex App 外部增强和 CDP 注入。
- Provider 同步和会话增强。

注意：

- 它是客户端增强工具，不是纯后端中转站。
- 如果目标是搭平台，不能只复制它，需要把 Provider 注入能力和后端路由能力拆开。

### 3. codex-provider-sync：历史会话修复

项目地址：https://github.com/Dailin521/codex-provider-sync

定位：切换 Codex Provider 后，让历史会话重新可见。

它同步的位置包括：

- `~/.codex/sessions`
- `~/.codex/archived_sessions`
- `~/.codex/state_5.sqlite`
- `.codex-global-state.json` 项目路径缓存

适合参考：

- Provider 切换后的会话 metadata 修复。
- Desktop `/resume` 和历史列表可见性问题。
- 备份和恢复机制。

注意：

- 它只修 metadata，不重写会话内容。
- 跨账号或跨 Provider 的 encrypted content 不一定能继续对话。

### 4. codex-proxy：协议转换参考

项目地址：https://github.com/icebear0828/codex-proxy

定位：把 Codex Desktop 的 Responses API 能力转换成 OpenAI、Anthropic、Gemini 等协议给其他客户端用。

适合参考：

- Responses API 和 Chat Completions / Anthropic / Gemini 之间的协议转换。
- SSE 流式输出。
- 模型路由。
- 本地网关架构。
- Dashboard 和配置管理。

注意：

- 项目包含账号轮换、指纹伪装、反检测等敏感方向。
- 建议只参考协议转换和网关架构，不直接照搬风控规避相关逻辑。

## 推荐架构

### 第一层：Codex 客户端配置

Codex 配置目标是固定 Provider 名。

示例：

```toml
model_provider = "LocalCodexRelay"
model = "gpt-5.4-codex"

[model_providers.LocalCodexRelay]
name = "LocalCodexRelay"
base_url = "http://127.0.0.1:3000/v1"
wire_api = "responses"
experimental_bearer_token = "sk-local-user-key"
requires_openai_auth = true
web_search = "live"
supports_websockets = false
```

关键点：

- `wire_api = "responses"` 必须保留。
- `base_url` 指向自己的中转网关。
- `experimental_bearer_token` 是用户在中转站生成的 Key。
- Provider 名尽量不要频繁变化。

### 第二层：Codex Relay 网关

网关必须实现：

- `POST /v1/responses`
- `GET /v1/models`
- API Key 鉴权
- SSE 流式转发
- 错误码透传和标准化
- 请求日志脱敏
- 用量统计
- 上游路由

建议内部模块：

```text
src/
  server/              HTTP 服务
  auth/                API Key 鉴权
  responses/           /v1/responses 处理
  models/              模型列表
  routing/             上游选择、故障转移
  billing/             token 统计、余额扣费
  providers/           OpenAI / sub2api / 自定义 Provider
  storage/             用户、Key、用量、上游配置
  admin/               管理后台 API
```

### 第三层：上游 Provider

第一版建议只接一种上游：

```text
LocalCodexRelay -> 单个 Responses API 上游
```

第二版再扩展：

```text
LocalCodexRelay
  -> Provider A
  -> Provider B
  -> sub2api
  -> OpenAI 官方
```

路由策略：

- 按模型名路由。
- 按用户组路由。
- 按余额/套餐路由。
- 按失败率故障转移。
- 按延迟和并发动态调度。

## 自用版路线

当前目标是个人自用，不做商业化。因此第一版不需要完整用户系统、支付系统和公开账号池，应该先做“单用户本地 Codex 路由器”。

自用版目标：

- 使用自己的 ChatGPT Free / Plus 登录态。
- 使用自己的 OpenAI API Key、第三方 Codex 中转 Key 或自建 Provider。
- Codex 侧固定连接本机 `LocalCodexRelay`。
- 后端负责切换真实上游、失败重试、用量记录和限速。
- 不做账号共享，不做批量注册，不做风控绕过。

推荐结构：

```text
Codex CLI / Codex App / Codex Desktop
  -> http://127.0.0.1:3000/v1/responses
  -> LocalCodexRelay
  -> 自己的上游 Key / 自己的第三方 Provider / 自建 sub2api
```

自用版可以做：

- 固定 Provider 名，避免会话和移动端状态混乱。
- 多上游配置，例如主力上游、备用上游、低价上游。
- 按模型名路由，例如 `gpt-5.4-codex` 走上游 A，`gpt-5.4-mini` 走上游 B。
- 本地用量统计和余额提醒，避免误刷额度。
- 请求失败自动切备用上游。
- `~/.codex` 状态备份。
- 参考 codex-provider-sync 修复 Provider 切换后的历史会话可见性。

自用版不建议做：

- 批量注册免费账号。
- 绕过手机号、OTP 或登录验证。
- Plus 账号池。
- 多人共享 Plus。
- 自动化规避限流或风控。
- 把个人 ChatGPT 登录态转卖或开放给他人使用。

### 自用配置建议

`~/.codex/config.toml` 固定写一个本机 Provider：

```toml
model_provider = "LocalCodexRelay"
model = "gpt-5.4-codex"

[model_providers.LocalCodexRelay]
name = "LocalCodexRelay"
base_url = "http://127.0.0.1:3000/v1"
wire_api = "responses"
experimental_bearer_token = "sk-local"
requires_openai_auth = true
web_search = "live"
supports_websockets = false
```

本地中转配置可以用一个简单的配置文件开始：

```toml
[server]
host = "127.0.0.1"
port = 3000

[[providers]]
id = "primary"
name = "Primary Codex Provider"
base_url = "https://example-provider-a.com/v1"
api_key_env = "PRIMARY_CODEX_API_KEY"
wire_api = "responses"
priority = 10

[[providers]]
id = "backup"
name = "Backup Codex Provider"
base_url = "https://example-provider-b.com/v1"
api_key_env = "BACKUP_CODEX_API_KEY"
wire_api = "responses"
priority = 20

[[routes]]
model = "gpt-5.4-codex"
provider = "primary"
fallback = ["backup"]

[[routes]]
model = "gpt-5.4-mini"
provider = "backup"
```

自用版环境变量：

```bash
export PRIMARY_CODEX_API_KEY="sk-..."
export BACKUP_CODEX_API_KEY="sk-..."
export HTTP_PROXY="http://127.0.0.1:7897"
export HTTPS_PROXY="http://127.0.0.1:7897"
export ALL_PROXY="http://127.0.0.1:7897"
export NO_PROXY="localhost,127.0.0.1,::1"
```

### 自用版 MVP 顺序

1. 先实现一个只监听 `127.0.0.1` 的本地服务。
2. 只支持自己的一个 `sk-local`。
3. 只透传 `/v1/responses` 到一个上游。
4. 跑通 Codex CLI。
5. 再加备用上游和模型路由。
6. 最后再做用量统计、状态备份和会话 metadata 修复。

## MVP 实施路线

### 阶段 1：最小可用中转

目标：Codex 能通过自己的网关完成一次 `/v1/responses` 调用。

实现：

- HTTP 服务。
- `POST /v1/responses` 透传。
- Bearer Key 鉴权。
- 单上游配置。
- SSE 流式响应。
- 基础日志。

验收：

```bash
curl http://127.0.0.1:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local-user-key" \
  -d '{
    "model": "gpt-5.4-codex",
    "input": "hello"
  }'
```

### 阶段 2：Codex 客户端接入

目标：Codex CLI / App 能稳定走本地中转。

实现：

- 写入 `~/.codex/config.toml` 的固定 Provider。
- 保留 `wire_api = "responses"`。
- 保留 Provider 名不变，只在服务端切上游。
- 加 `.env` 代理配置。

本机代理端口是：

```env
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
ALL_PROXY=http://127.0.0.1:7897
NO_PROXY=localhost,127.0.0.1,::1
```

### 阶段 3：用户和计费

目标：从“自己用”变成“可分发 Key”。

实现：

- 用户表。
- API Key 表。
- 上游 Key 表。
- 请求量、输入 token、输出 token 记录。
- 余额扣费。
- 限流。
- Key 启停。

### 阶段 4：多上游和故障转移

目标：把真实上游变化藏在固定 Provider 后面。

实现：

- Provider 配置表。
- 模型映射表。
- 健康检查。
- 熔断和重试。
- Sticky session。
- 按模型、用户组、成本路由。

### 阶段 5：Codex App 增强兼容

目标：支持更完整的 Codex App 使用体验。

参考 Codex++：

- 中转注入。
- ChatGPT 登录态保留。
- Provider 固定。
- 插件入口和会话功能增强。

参考 codex-provider-sync：

- 切 Provider 后同步历史会话 metadata。
- 备份 `~/.codex` 状态。
- 恢复工具。

## 数据模型草案

### users

```text
id
email
status
balance
created_at
updated_at
```

### api_keys

```text
id
user_id
name
key_hash
status
rate_limit_rpm
rate_limit_tpm
created_at
last_used_at
```

### providers

```text
id
name
base_url
api_key_encrypted
wire_api
status
priority
weight
created_at
updated_at
```

### model_routes

```text
id
public_model
provider_id
upstream_model
enabled
priority
```

### usage_logs

```text
id
user_id
api_key_id
provider_id
request_id
model
input_tokens
output_tokens
cost
status
created_at
```

## 关键兼容点

### Responses API 请求

必须保留 Codex 需要的字段，不要按 Chat Completions 思路强行改写。

重点关注：

- `input`
- `instructions`
- `previous_response_id`
- reasoning items
- tool calls
- stream events
- response id
- usage

### 流式响应

Codex 对流式事件比较敏感，建议第一版做透明转发。

不要过早做复杂转换，先保证：

- SSE headers 正确。
- 不缓存流式响应。
- 断线能关闭上游连接。
- 错误事件格式尽量贴近上游。

### Provider 名固定

社区实测中，频繁切 `model_provider`、`base_url` 或 Key，可能导致：

- 移动端离线。
- 历史会话不可见。
- Desktop 最近列表异常。
- 旧会话 encrypted content 无法继续。

因此建议：

- Codex 侧固定 `model_provider = "LocalCodexRelay"`。
- 后端自己切真实上游。
- 不让用户直接改 Codex Provider。

## 风险边界

当前项目定位是个人自用。个人自用可以做本机自动化、自带账号接入和本地 Provider 路由，但仍然不建议走账号农场、绕验证、共享 Plus 和规避风控路线。

建议避免的方向：

- 大规模账号轮换。
- 指纹伪装。
- 绕过平台风控。
- 批量注册免费账号。
- 绕过手机号、OTP 或登录验证。
- Plus 账号池或多人共用 Plus。
- 把个人 ChatGPT 会话能力公开售卖。
- 明文存储上游 Key。
- 日志记录完整 prompt、token、cookie 或账号凭据。

建议坚持的方向：

- 做单用户本地 Codex 路由器。
- 做 Responses API 兼容网关。
- 做合法 API Key 管理和用量统计。
- 做透明的上游配置。
- 做日志脱敏。
- 做用户自己的 Key 或自有上游接入。
- 做失败重试、限流和成本控制。

## 本机浏览器调研环境

本机使用 WSL 内的 Linux 版 Google Chrome，不走 Windows Chrome。

Chrome 148 开启 remote debugging 需要非默认 profile，可用命令：

```bash
google-chrome --remote-debugging-port=9333 \
  --proxy-server=http://127.0.0.1:7897 \
  --user-data-dir=/tmp/codex-wsl-chrome-9333 \
  --no-first-run --no-default-browser-check about:blank
```

如果 `web-access` 自动发现失败，可手动写：

```text
~/.config/google-chrome/DevToolsActivePort
```

内容格式：

```text
9333
/devtools/browser/<actual-browser-id>
```

然后运行：

```bash
node /home/lzy/.cc-switch/skills/web-access/scripts/check-deps.mjs --browser chrome
```

## 下一步建议

优先做 MVP：

1. 初始化后端项目。
2. 实现 `POST /v1/responses` 透明代理。
3. 增加本地 API Key 鉴权。
4. 固定 Codex Provider 指向本地网关。
5. 跑通 Codex CLI 一次真实请求。

MVP 跑通后，再决定是：

- 接入 sub2api 做平台底座。
- 自己实现轻量平台。
- 做 Codex++ 式客户端注入工具。
- 做 provider-sync 风格的会话修复工具。
