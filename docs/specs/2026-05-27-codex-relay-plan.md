# Codex Relay 实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 构建一个完整的 Codex Responses API 中转网关，支持多上游、故障转移、用户计费、限流、管理后台。

**Architecture:** Go + Gin 单体应用，SQLite 存储，嵌入式管理前端。透明代理 /v1/responses，异步记录用量。

**Tech Stack:** Go 1.22+, Gin, SQLite (mattn/go-sqlite3), go:embed, Alpine.js + TailwindCSS CDN

**设计文档:** `docs/specs/2026-05-27-codex-relay-design.md`

---

## 阶段 1：项目骨架 + 配置

### Task 1: 初始化 Go 模块和目录结构

**Objective:** 创建 Go 项目骨架，所有目录和空文件就位

**Files:**
- Create: `go.mod`
- Create: `cmd/server/main.go`
- Create: `internal/config/config.go`
- Create: `internal/database/db.go`
- Create: `.env.example`
- Create: `Makefile`

**Step 1: 初始化 Go 模块**

```bash
cd /home/lzy/project/项目-api中转站
go mod init codex-relay
```

**Step 2: 创建目录结构**

```bash
mkdir -p cmd/server
mkdir -p internal/{config,database,middleware,handler/admin,proxy,model,store}
mkdir -p web
```

**Step 3: 写 go.mod**

```go
module codex-relay

go 1.22
```

**Step 4: 安装核心依赖**

```bash
go get github.com/gin-gonic/gin
go get github.com/mattn/go-sqlite3
go get github.com/joho/godotenv
go get golang.org/x/crypto/bcrypt
```

**Step 5: 验证**

```bash
go mod tidy
go build ./...
```

Expected: 无报错

**Step 6: Commit**

```bash
git init && git add -A && git commit -m "chore: init go project skeleton"
```

---

### Task 2: 配置加载

**Objective:** 从 .env 文件加载所有配置项

**Files:**
- Create: `internal/config/config.go`
- Create: `.env.example`

**Step 1: 写 .env.example**

```env
PORT=3000
ADMIN_KEY=change-me-to-a-strong-secret
DATABASE_PATH=data/codex_relay.db
HTTP_PROXY=
HTTPS_PROXY=
LOG_LEVEL=info
ENCRYPTION_KEY=change-me-32-bytes-for-aes-256
```

**Step 2: 写 internal/config/config.go**

```go
package config

import (
    "os"
    "github.com/joho/godotenv"
)

type Config struct {
    Port          string
    AdminKey      string
    DatabasePath  string
    HTTPProxy     string
    HTTPSProxy    string
    LogLevel      string
    EncryptionKey string
}

func Load() *Config {
    godotenv.Load()
    return &Config{
        Port:          getEnv("PORT", "3000"),
        AdminKey:      getEnv("ADMIN_KEY", ""),
        DatabasePath:  getEnv("DATABASE_PATH", "data/codex_relay.db"),
        HTTPProxy:     getEnv("HTTP_PROXY", ""),
        HTTPSProxy:    getEnv("HTTPS_PROXY", ""),
        LogLevel:      getEnv("LOG_LEVEL", "info"),
        EncryptionKey: getEnv("ENCRYPTION_KEY", ""),
    }
}

func getEnv(key, fallback string) string {
    if v := os.Getenv(key); v != "" {
        return v
    }
    return fallback
}
```

**Step 3: 验证**

```bash
go build ./internal/config/
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add config loading from .env"
```

---

### Task 3: 数据库初始化 + 建表

**Objective:** SQLite 连接 + 建立所有表

**Files:**
- Create: `internal/database/db.go`

**Step 1: 写 internal/database/db.go**

建表 SQL 按设计文档中的 5 张表实现（users, api_keys, providers, model_routes, usage_logs）。包含索引。

**Step 2: 验证**

```bash
go build ./internal/database/
```

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: sqlite database init with all tables"
```

---

## 阶段 2：数据模型 + Store 层

### Task 4: User 模型和 Store

**Objective:** 用户 CRUD 操作

**Files:**
- Create: `internal/model/user.go`
- Create: `internal/store/user.go`

**Step 1:** 写 model（struct 定义）
**Step 2:** 写 store（Create, GetByID, GetByEmail, List, Update, Delete）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: user model and store`

---

### Task 5: API Key 模型和 Store

**Objective:** API Key CRUD + 哈希生成

**Files:**
- Create: `internal/model/apikey.go`
- Create: `internal/store/apikey.go`

**Step 1:** 写 model（含生成 Key、SHA256 哈希的工具函数）
**Step 2:** 写 store（Create, GetByHash, ListByUser, Update, Delete）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: apikey model and store`

---

### Task 6: Provider 模型和 Store

**Objective:** 上游 Provider CRUD

**Files:**
- Create: `internal/model/provider.go`
- Create: `internal/store/provider.go`

**Step 1:** 写 model（含 AES 加解密工具函数）
**Step 2:** 写 store（Create, GetByID, List, Update, Delete）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: provider model and store`

---

### Task 7: Model Route 模型和 Store

**Objective:** 模型路由 CRUD

**Files:**
- Create: `internal/model/route.go`
- Create: `internal/store/route.go`

**Step 1:** 写 model
**Step 2:** 写 store（Create, List, FindRoute(publicModel, userGroup), Update, Delete）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: model route and store`

---

### Task 8: Usage Log 模型和 Store

**Objective:** 用量日志写入和查询

**Files:**
- Create: `internal/model/usage.go`
- Create: `internal/store/usage.go`

**Step 1:** 写 model
**Step 2:** 写 store（Create, Query(filters), Dashboard summary）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: usage log model and store`

---

## 阶段 3：中间件

### Task 9: API Key 鉴权中间件

**Objective:** 从 Authorization header 提取 Key，查表验证

**Files:**
- Create: `internal/middleware/auth.go`

**Step 1:** 写中间件：提取 Bearer token → SHA256 → 查 api_keys 表 → 注入 user_id/key_id 到 gin.Context
**Step 2:** 验证编译
**Step 3:** Commit: `feat: bearer token auth middleware`

---

### Task 10: Admin Key 鉴权中间件

**Objective:** 管理接口用固定 Admin Key 鉴权

**Files:**
- Create: `internal/middleware/admin_auth.go`

**Step 1:** 写中间件：比较 Authorization header 与配置中的 AdminKey
**Step 2:** 验证编译
**Step 3:** Commit: `feat: admin key auth middleware`

---

### Task 11: 请求日志中间件

**Objective:** 记录每个请求的方法、路径、状态码、耗时

**Files:**
- Create: `internal/middleware/logger.go`

**Step 1:** 写 Gin 日志中间件
**Step 2:** 验证编译
**Step 3:** Commit: `feat: request logger middleware`

---

## 阶段 4：核心代理

### Task 12: 上游路由器

**Objective:** 根据 model_routes 选择最佳 provider

**Files:**
- Create: `internal/proxy/router.go`

**Step 1:** 实现路由逻辑：
1. 查 model_routes 匹配 public_model
2. 按 priority 排序
3. 过滤 status=active 的 provider
4. 按 weight 加权随机选择
**Step 2:** 验证编译
**Step 3:** Commit: `feat: upstream provider router`

---

### Task 13: 熔断器

**Objective:** 连续失败超阈值自动熔断

**Files:**
- Create: `internal/proxy/circuit_breaker.go`

**Step 1:** 实现熔断器：
- 每个 provider 维护 failure_count + last_failure_time
- 连续失败 >= threshold → 状态变 open
- 经过 recovery_seconds → 状态变 half-open，允许一次请求
- 成功 → closed，失败 → 重新 open
**Step 2:** 验证编译
**Step 3:** Commit: `feat: circuit breaker per provider`

---

### Task 14: /v1/models 端点

**Objective:** 返回可用模型列表

**Files:**
- Create: `internal/handler/models.go`

**Step 1:** 实现 handler：查 model_routes 去重 → 返回 OpenAI 兼容格式
**Step 2:** 验证编译
**Step 3:** Commit: `feat: GET /v1/models endpoint`

---

### Task 15: /v1/responses 非流式转发

**Objective:** 处理 stream=false 的请求

**Files:**
- Create: `internal/handler/responses.go`
- Create: `internal/proxy/forwarder.go`

**Step 1:** 实现 forwarder：
- 读取请求体 → 解析 model
- 调用 router 选 provider
- 替换 Authorization + model
- 转发到上游 base_url + /responses
- 读响应 → 返回给客户端
**Step 2:** 实现 handler：调用 forwarder
**Step 3:** 验证编译
**Step 4:** Commit: `feat: POST /v1/responses non-streaming`

---

### Task 16: /v1/responses SSE 流式转发

**Objective:** 处理 stream=true 的请求

**Files:**
- Modify: `internal/proxy/forwarder.go`

**Step 1:** 实现 SSE 转发：
- 检测 stream=true
- 设置响应头：Content-Type: text/event-stream
- 逐行读取上游 SSE 事件 → 写入客户端
- 处理客户端断开（context cancel）
**Step 2:** 验证编译
**Step 3:** Commit: `feat: SSE streaming for /v1/responses`

---

## 阶段 5：计费和限流

### Task 17: 用量记录

**Objective:** 从响应中提取 usage，异步写入 usage_logs

**Files:**
- Create: `internal/billing/billing.go`

**Step 1:** 实现：
- 从响应 JSON 中提取 usage.input_tokens / usage.output_tokens
- 计算 cost（可配置单价表）
- goroutine 异步写入 usage_logs
- 扣减用户余额
**Step 2:** 验证编译
**Step 3:** Commit: `feat: async usage logging and balance deduction`

---

### Task 18: 限流中间件

**Objective:** 按 API Key 的 RPM/TPM 限制请求

**Files:**
- Create: `internal/middleware/rate_limit.go`

**Step 1:** 实现令牌桶限流：
- 每个 key 维护 rpm 和 tpm 计数器
- 每分钟重置
- 超限返回 429
**Step 2:** 验证编译
**Step 3:** Commit: `feat: per-key rate limiting (RPM/TPM)`

---

## 阶段 6：管理后台 API

### Task 19: 用户管理 API

**Objective:** 用户 CRUD 端点

**Files:**
- Create: `internal/handler/admin/user.go`

**Step 1:** 实现 POST/GET/PUT/DELETE /admin/users
**Step 2:** 验证编译
**Step 3:** Commit: `feat: admin user CRUD API`

---

### Task 20: API Key 管理 API

**Objective:** Key CRUD 端点

**Files:**
- Create: `internal/handler/admin/apikey.go`

**Step 1:** 实现 POST/GET/PUT/DELETE /admin/apikeys
- POST 时生成 Key，返回明文一次
**Step 2:** 验证编译
**Step 3:** Commit: `feat: admin apikey CRUD API`

---

### Task 21: Provider 管理 API

**Objective:** Provider CRUD + 连通性测试

**Files:**
- Create: `internal/handler/admin/provider.go`

**Step 1:** 实现 POST/GET/PUT/DELETE /admin/providers
**Step 2:** 实现 POST /admin/providers/:id/test（发一个简单请求测试上游）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: admin provider CRUD + test endpoint`

---

### Task 22: 模型路由管理 API

**Objective:** 路由 CRUD

**Files:**
- Create: `internal/handler/admin/route.go`

**Step 1:** 实现 POST/GET/PUT/DELETE /admin/routes
**Step 2:** 验证编译
**Step 3:** Commit: `feat: admin model route CRUD API`

---

### Task 23: 用量查询 + 仪表盘 API

**Objective:** 用量查询和汇总

**Files:**
- Create: `internal/handler/admin/usage.go`
- Create: `internal/handler/admin/dashboard.go`

**Step 1:** 实现 GET /admin/usage（支持 user_id / 时间范围过滤）
**Step 2:** 实现 GET /admin/dashboard（今日请求总数、token 总数、收入、活跃用户数）
**Step 3:** 验证编译
**Step 4:** Commit: `feat: admin usage query and dashboard API`

---

## 阶段 7：嵌入式管理前端

### Task 24: 管理仪表盘 HTML

**Objective:** 单文件嵌入式管理页面

**Files:**
- Create: `web/index.html`
- Modify: `cmd/server/main.go`（go:embed）

**Step 1:** 用 Alpine.js + TailwindCSS CDN 写单文件 SPA
- 侧边栏导航：仪表盘 / 用户 / Key / Provider / 路由 / 用量
- 每个页面对应管理 API 的表格 + 表单
- 登录框（Admin Key）
**Step 2:** 在 main.go 中用 go:embed 嵌入
**Step 3:** 验证编译
**Step 4:** Commit: `feat: embedded admin dashboard`

---

## 阶段 8：入口 + 路由注册

### Task 25: main.go 组装

**Objective:** 把所有组件串起来

**Files:**
- Modify: `cmd/server/main.go`

**Step 1:** 实现 main():
1. 加载配置
2. 初始化数据库
3. 创建 Gin engine
4. 注册中间件
5. 注册 /v1/* 路由
6. 注册 /admin/* 路由
7. 注册 /dashboard 静态页面
8. 启动 HTTP server
**Step 2:** 验证编译 + 启动
**Step 3:** Commit: `feat: main entry point wiring all components`

---

### Task 26: Makefile

**Objective:** 构建和运行脚本

**Files:**
- Create: `Makefile`

```makefile
.PHONY: build run clean

build:
	go build -o bin/codex-relay ./cmd/server/

run: build
	./bin/codex-relay

clean:
	rm -rf bin/ data/

dev:
	go run ./cmd/server/
```

**Step 1:** 写 Makefile
**Step 2:** Commit: `chore: add Makefile`

---

## 阶段 9：端到端验证

### Task 27: curl 验证

**Objective:** 用 curl 跑通完整流程

**Step 1:** 启动服务
```bash
make dev
```

**Step 2:** 创建用户和 Key（用 Admin Key）
```bash
# 创建用户
curl -X POST http://127.0.0.1:3000/admin/users \
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# 创建 API Key
curl -X POST http://127.0.0.1:3000/admin/apikeys \
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"name":"test-key"}'
# 记住返回的 sk-xxx 明文
```

**Step 3:** 创建上游 Provider
```bash
curl -X POST http://127.0.0.1:3000/admin/providers \
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"openai","base_url":"https://api.openai.com/v1","api_key":"sk-xxx"}'
```

**Step 4:** 创建模型路由
```bash
curl -X POST http://127.0.0.1:3000/admin/routes \
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"public_model":"gpt-5.4-codex","provider_id":1,"upstream_model":"gpt-5.4-codex"}'
```

**Step 5:** 测试 Responses API
```bash
curl http://127.0.0.1:3000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-relay-key" \
  -d '{"model":"gpt-5.4-codex","input":"hello"}'
```

**Step 6:** 测试模型列表
```bash
curl http://127.0.0.1:3000/v1/models \
  -H "Authorization: Bearer sk-your-relay-key"
```

**Step 7:** Commit: `docs: add curl verification examples`

---

## 任务执行顺序

```
Task 1-3:   骨架 + 配置 + 数据库     (基础)
Task 4-8:   数据模型 + Store          (基础)
Task 9-11:  中间件                    (基础)
Task 12-16: 核心代理                  (核心功能)
Task 17-18: 计费 + 限流              (核心功能)
Task 19-23: 管理后台 API             (管理功能)
Task 24:    嵌入式前端               (管理功能)
Task 25-26: 入口组装 + Makefile      (集成)
Task 27:    端到端验证               (验收)
```

总计 27 个任务，每个 2-5 分钟。预计总时间 1-2 小时。
