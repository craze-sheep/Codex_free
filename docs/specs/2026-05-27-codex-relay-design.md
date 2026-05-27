# Codex Relay 设计文档

日期: 2026-05-27
状态: 已批准（自主决策）

## 1. 项目定位

面向 Codex CLI / Codex App / Codex Desktop 的专用 API 中转站。

核心价值：用户永远只看到一个固定 Provider（LocalCodexRelay），后端自动切换真实上游、故障转移、计费。用户不需要关心上游是谁。

## 2. 技术栈

| 层 | 选型 | 理由 |
|---|------|------|
| 后端语言 | Go 1.22+ | 高并发、单二进制部署 |
| HTTP 框架 | Gin | 成熟、性能好、中间件生态丰富 |
| 数据库 | SQLite (WAL 模式) | 轻量、单文件、初期够用 |
| 前端 | 嵌入式 HTML + Alpine.js + TailwindCSS | 零构建依赖，go:embed 嵌入 |
| SSE 转发 | net/http 标准库 | 标准 SSE 无需额外依赖 |

## 3. 架构

```
┌──────────────────────────────────────────────┐
│                 codex-relay                   │
│                                              │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ /v1/*   │  │ /admin/* │  │ /dashboard  │ │
│  │ Codex   │  │ 管理 API │  │ 嵌入式前端  │ │
│  │ API     │  │          │  │             │ │
│  └────┬────┘  └────┬─────┘  └─────────────┘ │
│       │            │                         │
│  ┌────▼────────────▼──────────────────────┐  │
│  │           middleware                    │  │
│  │  auth → rate_limit → logging           │  │
│  └────┬───────────────────────────────────┘  │
│       │                                      │
│  ┌────▼──────────────────────────────────┐   │
│  │        proxy / routing                 │   │
│  │  model_route → provider_select →      │   │
│  │  circuit_breaker → upstream_call      │   │
│  └────┬──────────────────────────────────┘   │
│       │                                      │
│  ┌────▼──────────────────────────────────┐   │
│  │        billing / storage               │   │
│  │  usage_log → balance_deduct            │   │
│  └───────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐        ┌──────────┐
   │ OpenAI   │        │ 第三方   │
   │ 官方 API │        │ 中转上游 │
   └──────────┘        └──────────┘
```

## 4. 目录结构

```
codex-relay/
├── cmd/
│   └── server/
│       └── main.go              入口：加载配置 → 初始化DB → 启动Gin
├── internal/
│   ├── config/
│   │   └── config.go            配置结构体 + .env 加载
│   ├── database/
│   │   ├── db.go                SQLite 连接 + 建表
│   │   └── migrate.go           迁移逻辑
│   ├── middleware/
│   │   ├── auth.go              Bearer Token 鉴权
│   │   ├── admin_auth.go        Admin Key 鉴权
│   │   ├── rate_limit.go        令牌桶限流
│   │   └── logger.go            请求日志
│   ├── handler/
│   │   ├── responses.go         POST /v1/responses 核心代理
│   │   ├── models.go            GET /v1/models
│   │   └── admin/
│   │       ├── user.go          用户 CRUD
│   │       ├── apikey.go        API Key CRUD
│   │       ├── provider.go      上游 Provider CRUD
│   │       ├── route.go         模型路由 CRUD
│   │       ├── usage.go         用量查询
│   │       └── dashboard.go     仪表盘数据
│   ├── proxy/
│   │   ├── forwarder.go         请求转发（流式 + 非流式）
│   │   ├── router.go            上游选择逻辑
│   │   └── circuit_breaker.go   熔断器
│   ├── model/
│   │   ├── user.go              用户结构体
│   │   ├── apikey.go            API Key 结构体
│   │   ├── provider.go          Provider 结构体
│   │   ├── route.go             模型路由结构体
│   │   └── usage.go             用量日志结构体
│   └── store/
│       ├── user.go              用户 DB 操作
│       ├── apikey.go            API Key DB 操作
│       ├── provider.go          Provider DB 操作
│       ├── route.go             模型路由 DB 操作
│       └── usage.go             用量 DB 操作
├── web/
│   └── index.html               嵌入式管理页面（单文件 SPA）
├── go.mod
├── go.sum
├── .env.example
├── Makefile
└── README.md
```

## 5. 数据模型

### users
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| email | TEXT UNIQUE | 邮箱 |
| password_hash | TEXT | bcrypt 密码哈希 |
| role | TEXT | admin / user |
| status | TEXT | active / suspended |
| balance | REAL | 余额（美元） |
| created_at | TEXT | 创建时间 |

### api_keys
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| user_id | INTEGER FK | 关联用户 |
| name | TEXT | Key 名称 |
| key_hash | TEXT UNIQUE | SHA256 哈希 |
| key_prefix | TEXT | sk-xxxx 前 12 位，用于展示 |
| status | TEXT | active / suspended |
| rate_limit_rpm | INTEGER | 每分钟请求数限制 |
| rate_limit_tpm | INTEGER | 每分钟 token 限制 |
| created_at | TEXT | 创建时间 |
| last_used_at | TEXT | 最后使用时间 |

### providers
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| name | TEXT UNIQUE | 如 openai_official, sub2api_pool |
| base_url | TEXT | 上游 /v1 地址 |
| api_key_encrypted | TEXT | AES 加密的上游 Key |
| wire_api | TEXT | responses / chat_completions |
| status | TEXT | active / disabled |
| priority | INTEGER | 越大越优先 |
| weight | INTEGER | 同优先级内的权重 |
| max_concurrency | INTEGER | 最大并发 |
| failure_threshold | INTEGER | 连续失败 N 次后熔断 |
| recovery_seconds | INTEGER | 熔断恢复秒数 |
| created_at | TEXT | 创建时间 |

### model_routes
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| public_model | TEXT | 用户请求的模型名，* 为通配 |
| provider_id | INTEGER FK | 关联 provider |
| upstream_model | TEXT | 上游实际模型名，空则透传 |
| user_group | TEXT | 适用用户组，* 为全部 |
| enabled | INTEGER | 1 启用 / 0 禁用 |
| priority | INTEGER | 越大越优先 |

### usage_logs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| user_id | INTEGER | 用户 ID |
| api_key_id | INTEGER | Key ID |
| provider_id | INTEGER | Provider ID |
| request_id | TEXT | 请求追踪 ID |
| model | TEXT | 模型名 |
| input_tokens | INTEGER | 输入 token 数 |
| output_tokens | INTEGER | 输出 token 数 |
| cost | REAL | 费用 |
| status | TEXT | success / error |
| latency_ms | INTEGER | 响应耗时 |
| created_at | TEXT | 创建时间 |

## 6. 核心接口

### 6.1 Codex API

**POST /v1/responses**
- 鉴权：Bearer Token（api_keys 表）
- 行为：解析 model → 查 model_routes → 选 provider → 转发
- 流式：stream=true 时逐行转发 SSE 事件
- 用量：异步记录 input_tokens / output_tokens / cost

**GET /v1/models**
- 返回所有已启用路由的 public_model 列表
- 格式兼容 OpenAI /v1/models 响应

### 6.2 管理 API（需 Admin Key）

**用户管理**
- POST /admin/users — 创建用户
- GET /admin/users — 用户列表
- PUT /admin/users/:id — 修改用户
- DELETE /admin/users/:id — 删除用户

**API Key 管理**
- POST /admin/apikeys — 创建 Key（返回明文 Key，仅此一次）
- GET /admin/apikeys — Key 列表
- PUT /admin/apikeys/:id — 修改限流/状态
- DELETE /admin/apikeys/:id — 删除 Key

**Provider 管理**
- POST /admin/providers — 创建上游
- GET /admin/providers — Provider 列表
- PUT /admin/providers/:id — 修改上游
- DELETE /admin/providers/:id — 删除上游
- POST /admin/providers/:id/test — 测试上游连通性

**模型路由管理**
- POST /admin/routes — 创建路由
- GET /admin/routes — 路由列表
- PUT /admin/routes/:id — 修改路由
- DELETE /admin/routes/:id — 删除路由

**用量统计**
- GET /admin/usage — 查询用量（支持 user_id / 时间范围过滤）
- GET /admin/dashboard — 仪表盘汇总（今日请求、token、收入、活跃用户）

## 7. 关键设计决策

1. **透明转发**：不改写请求/响应体，只替换 Authorization 和 model 字段。
2. **异步日志**：用量记录在独立 goroutine 中写入，不阻塞响应。
3. **熔断器**：每个 provider 维护连续失败计数，超过阈值自动跳过。
4. **Key 生成**：明文 Key 只在创建时返回一次，存储只存 SHA256 哈希。
5. **上游 Key 加密**：AES-256-GCM 加密存储，运行时解密。
6. **前端嵌入**：单个 index.html 用 go:embed 嵌入，零构建依赖。

## 8. 不做的事（YAGNI）

- 不做用户自助注册（第一版由管理员创建）
- 不做充值支付集成
- 不做 Chat Completions 协议转换
- 不做 Codex App 注入增强
- 不做会话同步
- 不做多数据库支持
