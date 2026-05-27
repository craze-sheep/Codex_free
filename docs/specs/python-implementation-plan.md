# Codex Relay (Python + FastAPI) 实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 构建一个完整的 Codex Responses API 中转网关，支持多上游、故障转移、用户计费、限流、管理后台。

**Architecture:** Python + FastAPI 单体应用，SQLite (aiosqlite) 存储，嵌入式管理前端。透明代理 /v1/responses，异步记录用量。

**Tech Stack:** Python 3.11, FastAPI, uvicorn, aiosqlite, httpx, httpx-sse, pydantic, python-dotenv

**设计文档:** `docs/specs/2026-05-27-codex-relay-design.md`
**技术路线:** `docs/codex-relay-technical-route.md`

---

## 阶段 1：项目骨架 + 配置

### Task 1: 项目目录结构

**Objective:** 创建 Python 项目骨架，所有目录和 __init__.py 就位

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `app/models/__init__.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/admin/__init__.py`
- Create: `app/proxy/__init__.py`
- Create: `app/middleware/__init__.py`
- Create: `app/store/__init__.py`

**Step 1:** 创建目录结构
```bash
cd /home/lzy/project/项目-api中转站
mkdir -p app/{models,routers/admin,proxy,middleware,store}
touch app/__init__.py app/models/__init__.py app/routers/__init__.py
touch app/routers/admin/__init__.py app/proxy/__init__.py
touch app/middleware/__init__.py app/store/__init__.py
```

**Step 2:** 验证目录就位
```bash
find app -type f | sort
```

**Step 3:** Commit
```bash
git add -A && git commit -m "chore: init python project skeleton"
```

---

### Task 2: 配置加载 (.env)

**Objective:** 从 .env 文件加载所有配置项，pydantic Settings

**Files:**
- Create: `app/config.py`

**Step 1:** 写 app/config.py
- 使用 pydantic BaseSettings 或 python-dotenv
- 配置项：PORT, ADMIN_KEY, DATABASE_URL, HTTP_PROXY, HTTPS_PROXY, LOG_LEVEL, ENCRYPTION_KEY

**Step 2:** 复制 .env.example 到 .env
```bash
cp .env.example .env
```

**Step 3:** 验证
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate codex-relay && python -c "from app.config import settings; print(settings)"
```

**Step 4:** Commit
```bash
git add -A && git commit -m "feat: add config loading from .env"
```

---

### Task 3: 数据库初始化 + 建表

**Objective:** aiosqlite 连接 + 建立所有表

**Files:**
- Create: `app/database.py`

**Step 1:** 写 app/database.py
- aiosqlite 连接管理 (async context manager)
- WAL 模式
- 建表 SQL：users, api_keys, providers, model_routes, usage_logs
- 包含索引

**Step 2:** 验证
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate codex-relay && python -c "from app.database import init_db; import asyncio; asyncio.run(init_db()); print('OK')"
```

**Step 3:** Commit
```bash
git add -A && git commit -m "feat: sqlite database init with all tables"
```

---

## 阶段 2：数据模型 + Store 层

### Task 4: Pydantic 模型定义

**Objective:** 所有数据模型的 Pydantic schema

**Files:**
- Create: `app/models/schemas.py`

**Step 1:** 定义 Pydantic models
- UserCreate, UserUpdate, UserResponse
- ApiKeyCreate, ApiKeyResponse
- ProviderCreate, ProviderUpdate, ProviderResponse
- RouteCreate, RouteUpdate, RouteResponse
- UsageQuery, UsageResponse, DashboardSummary

**Step 2:** 验证 import
```bash
python -c "from app.models.schemas import UserCreate; print('OK')"
```

**Step 3:** Commit
```bash
git add -A && git commit -m "feat: pydantic model schemas"
```

---

### Task 5: User Store

**Objective:** 用户 CRUD 操作 (async)

**Files:**
- Create: `app/store/user.py`

**Step 1:** 实现 async 函数
- create_user, get_user_by_id, get_user_by_email
- list_users, update_user, delete_user

**Step 2:** 验证
```bash
python -c "from app.store.user import *; print('OK')"
```

**Step 3:** Commit
```bash
git add -A && git commit -m "feat: user store (async CRUD)"
```

---

### Task 6: API Key Store

**Objective:** API Key CRUD + SHA256 哈希生成

**Files:**
- Create: `app/store/apikey.py`

**Step 1:** 实现
- generate_api_key() -> 明文 key + hash
- create_api_key, get_key_by_hash, list_keys_by_user
- update_key, delete_key

**Step 2:** Commit: `feat: apikey store`

---

### Task 7: Provider Store

**Objective:** 上游 Provider CRUD

**Files:**
- Create: `app/store/provider.py`

**Step 1:** 实现
- create_provider, get_provider_by_id, list_providers
- update_provider, delete_provider
- AES 加解密辅助函数 (加密存储上游 API Key)

**Step 2:** Commit: `feat: provider store`

---

### Task 8: Model Route Store

**Objective:** 模型路由 CRUD

**Files:**
- Create: `app/store/route.py`

**Step 1:** 实现
- create_route, list_routes, find_route(public_model, user_group)
- update_route, delete_route

**Step 2:** Commit: `feat: model route store`

---

### Task 9: Usage Log Store

**Objective:** 用量日志写入和查询

**Files:**
- Create: `app/store/usage.py`

**Step 1:** 实现
- create_usage_log, query_usage(filters)
- dashboard_summary(today's stats)

**Step 2:** Commit: `feat: usage log store`

---

## 阶段 3：中间件

### Task 10: API Key 鉴权中间件

**Objective:** 从 Authorization header 提取 Key，查表验证

**Files:**
- Create: `app/middleware/auth.py`

**Step 1:** FastAPI Depends
- 提取 Bearer token → SHA256 → 查 api_keys 表 → 返回 user_id/key_id

**Step 2:** Commit: `feat: bearer token auth middleware`

---

### Task 11: Admin Key 鉴权

**Objective:** 管理接口用固定 Admin Key 鉴权

**Files:**
- Create: `app/middleware/admin_auth.py`

**Step 1:** FastAPI Depends
- 比较 Authorization header 与配置中的 ADMIN_KEY

**Step 2:** Commit: `feat: admin key auth middleware`

---

## 阶段 4：核心代理

### Task 12: 上游路由器

**Objective:** 根据 model_routes 选择最佳 provider

**Files:**
- Create: `app/proxy/router.py`

**Step 1:** 实现
- 查 model_routes 匹配 public_model
- 按 priority 排序，过滤 active
- 按 weight 加权随机选择

**Step 2:** Commit: `feat: upstream provider router`

---

### Task 13: 熔断器

**Objective:** 连续失败超阈值自动熔断

**Files:**
- Create: `app/proxy/circuit_breaker.py`

**Step 1:** 实现
- 每个 provider 维护 failure_count + last_failure_time
- closed/open/half-open 状态机

**Step 2:** Commit: `feat: circuit breaker per provider`

---

### Task 14: /v1/models 端点

**Objective:** 返回可用模型列表

**Files:**
- Create: `app/routers/models.py`

**Step 1:** GET /v1/models → 查 model_routes 去重 → OpenAI 兼容格式

**Step 2:** Commit: `feat: GET /v1/models endpoint`

---

### Task 15: /v1/responses 非流式转发

**Objective:** 处理 stream=false 的请求

**Files:**
- Create: `app/proxy/forwarder.py`
- Create: `app/routers/responses.py`

**Step 1:** 实现 forwarder
- 读取请求体 → 解析 model
- 调用 router 选 provider
- 替换 Authorization + model
- 转发到上游 base_url + /responses
- 读响应 → 返回给客户端

**Step 2:** 实现 router endpoint

**Step 3:** Commit: `feat: POST /v1/responses non-streaming`

---

### Task 16: /v1/responses SSE 流式转发

**Objective:** 处理 stream=true 的请求

**Files:**
- Modify: `app/proxy/forwarder.py`

**Step 1:** 使用 httpx-sse 实现
- 检测 stream=true
- 设置 Content-Type: text/event-stream
- 逐行转发 SSE 事件
- 处理客户端断开

**Step 2:** Commit: `feat: SSE streaming for /v1/responses`

---

## 阶段 5：计费和限流

### Task 17: 用量记录

**Objective:** 从响应中提取 usage，异步写入 usage_logs

**Files:**
- Create: `app/billing.py`

**Step 1:** 实现
- 提取 usage.input_tokens / output_tokens
- asyncio.create_task 异步写入
- 扣减用户余额

**Step 2:** Commit: `feat: async usage logging and balance deduction`

---

### Task 18: 限流中间件

**Objective:** 按 API Key 的 RPM/TPM 限制请求

**Files:**
- Create: `app/middleware/rate_limit.py`

**Step 1:** 令牌桶限流
- 内存中按 key 维护计数器
- 超限返回 429

**Step 2:** Commit: `feat: per-key rate limiting (RPM/TPM)`

---

## 阶段 6：管理后台 API

### Task 19: 用户管理 API

**Files:** Create: `app/routers/admin/user.py`
- POST/GET/PUT/DELETE /admin/users
- Commit: `feat: admin user CRUD API`

### Task 20: API Key 管理 API

**Files:** Create: `app/routers/admin/apikey.py`
- POST/GET/PUT/DELETE /admin/apikeys
- POST 返回明文 Key 仅一次
- Commit: `feat: admin apikey CRUD API`

### Task 21: Provider 管理 API

**Files:** Create: `app/routers/admin/provider.py`
- POST/GET/PUT/DELETE /admin/providers
- POST /admin/providers/{id}/test
- Commit: `feat: admin provider CRUD + test endpoint`

### Task 22: 模型路由管理 API

**Files:** Create: `app/routers/admin/route.py`
- POST/GET/PUT/DELETE /admin/routes
- Commit: `feat: admin model route CRUD API`

### Task 23: 用量查询 + 仪表盘 API

**Files:** Create: `app/routers/admin/usage.py`
- GET /admin/usage (filters: user_id, time range)
- GET /admin/dashboard (today stats)
- Commit: `feat: admin usage query and dashboard API`

---

## 阶段 7：主入口 + 启动

### Task 24: main.py 整合所有路由

**Objective:** FastAPI app 注册所有路由和中间件

**Files:**
- Modify: `app/main.py`

**Step 1:** 创建 FastAPI app
- 注册所有 routers
- 添加 CORS 中间件
- startup 事件初始化 DB
- uvicorn 启动

**Step 2:** 验证启动
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate codex-relay
cd /home/lzy/project/项目-api中转站
python -m app.main
# 另一个终端测试
curl http://127.0.0.1:3000/v1/models
```

**Step 3:** Commit: `feat: main app entry with all routes`

---

## 阶段 8：嵌入式管理前端

### Task 25: 管理仪表盘 HTML

**Objective:** 单文件嵌入式管理页面

**Files:**
- Create: `static/index.html`
- Modify: `app/main.py` (StaticFiles mount)

**Step 1:** Alpine.js + TailwindCSS CDN 单文件 SPA
- 侧边栏：仪表盘 / 用户 / Key / Provider / 路由 / 用量

**Step 2:** Commit: `feat: embedded admin dashboard`

---

## 通用规范

- **conda 环境:** 所有 Python 命令必须在 `codex-relay` conda 环境中执行
- **提交规范:** feat/fix/chore/docs 前缀，每 task 一次 commit
- **错误处理:** 统一 JSON 错误响应格式
- **日志:** 使用 Python logging，配置级别从 .env 读取
- **代理:** httpx 请求时使用 .env 中的 HTTP_PROXY/HTTPS_PROXY
