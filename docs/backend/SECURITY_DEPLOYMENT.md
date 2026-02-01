# Security Deployment Guide

Phase 9.24: 安全部署指南（Codex 审查增强版 + Docker 支持）

> 提示（2026-02-01）：本文档包含检查清单与“待实现”等描述，用于安全部署审查，不代表当前开发待办；现状以 `docs/CURRENT_STATUS.md` 为准。

## ⚠️ 重要：默认安全部署模式

**强烈推荐使用反向代理注入模式**，而不是在前端配置 `VITE_ADMIN_API_KEY`。

```bash
# ❌ 不推荐 - 前端配置 Key（仅限内网）
VITE_ADMIN_API_KEY=your-key-here

# ✅ 推荐 - 不配置，由 Nginx 注入
# (前端不设置 VITE_ADMIN_API_KEY)
```

## 快速安全部署检查清单

在部署前，请确认以下事项：

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `VITE_ADMIN_API_KEY` 未在公网前端设置 | ⬜ | 防止 API Key 泄露 |
| `ADMIN_REQUIRE_API_KEY=true` | ⬜ | 强制启用 Admin 认证 |
| `ADMIN_API_KEY` 使用强密码 | ⬜ | `openssl rand -hex 32` |
| 反向代理注入 Admin Key | ⬜ | 由 Nginx 注入 Header |
| `TRUSTED_HOSTS` 已配置 | ⬜ | 防止 Host Header 攻击 |
| `CORS_ORIGINS` 仅包含生产域名 | ⬜ | 限制跨域请求来源 |
| `GENOMES_DIR` 使用专用目录 | ⬜ | 不混放敏感文件 |
| Admin 端点有 IP 白名单 | ⬜ | 限制访问来源 |

## Admin API 认证

### 问题背景

`VITE_ADMIN_API_KEY` 通过前端构建注入，会嵌入到 JavaScript 产物中。任何能访问前端文件的用户都可以通过以下方式提取 Key：
- 浏览器开发者工具查看源码
- 下载 dist 文件并搜索 "X-Admin-API-Key"

### 部署场景与建议

| 场景 | 风险 | 推荐方案 |
|------|------|----------|
| **公网部署 (反代)** | 低 | **✅ 默认推荐：Nginx 注入 Header** |
| 公网部署 (完整) | 低 | 后端实现会话式认证 |
| 内网/VPN 部署 | 低 | 可使用 `VITE_ADMIN_API_KEY` |
| 公网部署 (CDN) | **高** | **❌ 禁止使用**，Key 会泄露 |

### 方案 1: 反向代理注入 (✅ 默认推荐)

让 Nginx/Traefik 在服务端侧注入 Admin Key，前端不配置 `VITE_ADMIN_API_KEY`。

```nginx
# /etc/nginx/conf.d/lncrna-atlas.conf
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # Admin 端点 - 仅内网可访问 + 服务端注入 Key
    location /api/v1/admin {
        # IP 白名单
        allow 10.0.0.0/8;
        allow 192.168.0.0/16;
        allow 172.16.0.0/12;
        deny all;

        # 服务端注入 Admin Key（前端无需配置）
        proxy_set_header X-Admin-API-Key "your-secure-key-here";
        proxy_pass http://backend;
    }

    # 普通 API
    location /api/ {
        proxy_pass http://backend;
    }

    # 健康检查（后端为根路径 /health，不在 /api/v1 下）
    location = /health {
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_pass http://backend;
    }

    # 前端静态文件
    location / {
        root /var/www/lncrna-atlas/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

### 方案 2: 会话式认证

实现后端登录接口，使用 HttpOnly Cookie + CSRF Token：

```python
# 后端实现示例 (待实现)
@router.post("/admin/login")
async def admin_login(credentials: AdminCredentials, response: Response):
    if verify_admin(credentials):
        session_token = create_session()
        response.set_cookie(
            key="admin_session",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="strict"
        )
        return {"status": "ok"}
    raise HTTPException(401, "Invalid credentials")
```

### 方案 3: 内网部署

如果 Admin 页面仅在内网访问：
1. 确保前端只在内网可达
2. 可使用 `VITE_ADMIN_API_KEY`
3. 在网络层面限制外部访问

## /genomes 静态目录

### 风险

`/genomes` 端点暴露 `GENOMES_DIR` 下的所有文件。如果目录混放敏感文件，可能导致数据泄露。

### 安全配置

```bash
# 生产环境：使用专用目录
GENOMES_DIR=/data/genomes  # 仅放置公开的基因组文件

# 可选：禁用 /genomes 端点
GENOMES_DIR=  # 留空则禁用
```

### 允许的文件类型

`/genomes` 端点仅应包含：
- `.fa`, `.fasta` - 基因组序列
- `.fai` - FASTA 索引
- `.cytoband.txt` - 染色体带型
- `.chrom.sizes` - 染色体大小

**禁止放置：**
- `.env`, `.yaml`, `.json` 配置文件
- 数据库备份或导出文件
- 用户数据或私有信息

## CORS 配置

### 生产环境

```bash
# .env.production
CORS_ORIGINS=["https://your-domain.com"]
```

**不要使用：**
- `["*"]` - 允许所有来源
- `["http://localhost:3000"]` - 开发环境配置

### 检查清单

> 说明：本清单用于部署前自检（勾选表示已满足），不是开发待办；如与当前实现不一致，以 `docs/CURRENT_STATUS.md` 为准。
> Issue Template：`.github/ISSUE_TEMPLATE/security-deployment-checklist.yml`（推荐：每次创建一份新 issue 逐项勾选并留痕）
> 历史追踪：https://github.com/wyjistest/human-lncrna-atlas/issues/77（已迁移模板，作为历史记录）

- [ ] `VITE_ADMIN_API_KEY` 在公网部署时未设置
- [ ] 使用反向代理注入 Admin Key 或实现会话认证
- [ ] `GENOMES_DIR` 指向专用目录，无敏感文件
- [ ] `CORS_ORIGINS` 仅包含实际前端域名
- [ ] Admin 端点有 IP 白名单或二次认证

## 裸机/虚拟机部署方案（systemd + Nginx）

适用场景：你使用裸机/虚拟机部署，希望后端仅对本机监听，通过 Nginx 统一做 TLS、静态资源与 Admin Key 注入。

### 1) 后端（systemd）

建议把后端绑定到 `127.0.0.1:8000`，仅允许本机反代访问。

**环境变量（示例）**：`/etc/lncrna-atlas/backend.env`

> 提示：systemd `EnvironmentFile` 支持引号。`TRUSTED_HOSTS`/`CORS_ORIGINS` 是 JSON 数组，推荐用单引号包起来。

```bash
ENV=production

DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=lncrna
DB_PASSWORD=REPLACE_ME
DB_NAME=lncrna_production

# 连接池调参（可选；默认值已可用）
# - 稳定性优先：保持 DB_POOL_PRE_PING=true（默认）
# - 延迟极致优先：可尝试关闭 pre_ping，并用 recycle/timeout 控制断链风险（需压测验证）
# DB_POOL_SIZE=10
# DB_POOL_MAX_OVERFLOW=20
# DB_POOL_TIMEOUT=30
# DB_POOL_RECYCLE=1800
# DB_POOL_PRE_PING=true

ENABLE_CACHE=true
# 缓存 TTL 抖动：默认 0.1（±10%），可设为 0 禁用
# CACHE_TTL_JITTER_PCT=0.1
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

ADMIN_REQUIRE_API_KEY=true
ADMIN_API_KEY=REPLACE_ME

TRUSTED_HOSTS='["your-domain.com"]'
CORS_ORIGINS='["https://your-domain.com"]'

LOG_LEVEL=INFO

# 请求日志：默认全量（如需降低开销，见后文“生产日志回滚配置”）
REQUEST_LOG_ENABLED=true
REQUEST_LOG_SLOW_THRESHOLD_MS=0
REQUEST_LOG_SAMPLE_RATE=1.0
REQUEST_LOG_MAX_URL_LENGTH=2048
```

**关于 `DB_POOL_PRE_PING` 的验证建议**：

1. 默认保持开启（稳定性优先），观察一段时间的连接错误与 5xx。
2. 如要关闭（极端低延迟场景），建议先做压测对比 p95/p99，并模拟空闲断连（如长时间无请求或连接被代理/NAT 回收）验证是否出现 `server closed the connection unexpectedly` 等错误。
3. 发现错误立即回滚：重新设置 `DB_POOL_PRE_PING=true`，并结合 `DB_POOL_RECYCLE` 控制长连接寿命。

**生产日志回滚配置（降低 I/O）**：

- 仅记录慢请求：`REQUEST_LOG_SLOW_THRESHOLD_MS=200`（按需调整）
- 采样：`REQUEST_LOG_SAMPLE_RATE=0.1`（按需调整）
- 关闭请求日志：`REQUEST_LOG_ENABLED=false`

**systemd service（示例）**：`/etc/systemd/system/lncrna-atlas-backend.service`

> 注意：`WorkingDirectory`/`ExecStart` 请按你的实际部署目录调整；建议使用虚拟环境的 python/uvicorn。

```ini
[Unit]
Description=Human LncRNA Atlas Backend (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=lncrna
Group=lncrna
WorkingDirectory=/opt/human-lncrna-atlas/frontend/backend
EnvironmentFile=/etc/lncrna-atlas/backend.env
ExecStart=/opt/human-lncrna-atlas/frontend/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lncrna-atlas-backend
sudo systemctl status lncrna-atlas-backend
```

### 2) 前端（构建 + Nginx 静态托管）

1. 在构建前端时**不要设置** `VITE_ADMIN_API_KEY`（否则会进入构建产物）。
2. 将 `frontend/web/dist` 部署到 Nginx 的静态目录（示例见上文 Nginx 配置中的 `root /var/www/...`）。
3. 通过 Nginx 的 `location /api/v1/admin` 注入 `X-Admin-API-Key` 并配置 IP 白名单。

## 物化视图（MV）刷新与缓存无效化（运维闭环）

某些分析/导出接口在缺少物化视图时会走 fallback 路径（更慢）。数据导入后，如希望保持性能稳定，建议把 MV 刷新变成可重复、可回滚的运维动作，并在刷新后主动清理相关缓存。

推荐方式：使用脚本 `scripts/refresh_materialized_views.sh` 进行数据库侧刷新，并在脚本中用 Admin API 做 best-effort 的后端通知与缓存失效：

- MV 可用性缓存重置：`POST /api/v1/admin/mv-cache/reset`
- API 缓存命名空间失效：`POST /api/v1/admin/cache/invalidate/{namespace}`（白名单）
- 鉴权：`X-Admin-API-Key: <ADMIN_API_KEY>`（脚本支持 `ADMIN_API_KEY` 或 `HLA_ADMIN_API_KEY` 环境变量）

### systemd timer（示例）

1) 环境变量文件（示例）：`/etc/lncrna-atlas/mv-refresh.env`

```bash
# PostgreSQL（建议优先使用 ~/.pgpass；如用密码可用 DB_PASSWORD/PGPASSWORD 注入）
PGDATABASE=lncrna_production
PGHOST=127.0.0.1
PGPORT=5432
PGUSER=lncrna
DB_PASSWORD=REPLACE_ME

# Backend Admin API（仅服务端使用，避免进入前端构建产物）
BACKEND_URL=http://127.0.0.1:8000
HLA_ADMIN_API_KEY=REPLACE_ME

# 可选：仅失效部分 namespace（默认会失效全部允许列表）
# INVALIDATE_NAMESPACES=regulations,genes,stats,export
```

2) service（示例）：`/etc/systemd/system/lncrna-atlas-mv-refresh.service`

```ini
[Unit]
Description=Human LncRNA Atlas - Refresh Materialized Views
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=lncrna
Group=lncrna
WorkingDirectory=/opt/human-lncrna-atlas
EnvironmentFile=/etc/lncrna-atlas/mv-refresh.env
ExecStart=/opt/human-lncrna-atlas/scripts/refresh_materialized_views.sh --notify-backend --invalidate-cache
```

3) timer（示例）：`/etc/systemd/system/lncrna-atlas-mv-refresh.timer`

```ini
[Unit]
Description=Human LncRNA Atlas - MV Refresh (weekly)

[Timer]
OnCalendar=Sun 03:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lncrna-atlas-mv-refresh.timer
systemctl list-timers | rg lncrna-atlas-mv-refresh
```

### 回滚/止损

- 立即停止：禁用 timer（`systemctl disable --now lncrna-atlas-mv-refresh.timer`）
- 降低影响：改为 `--status` 仅检查，或减少刷新频率；必要时用 `-f/--full` 改为非并发刷新（注意锁与阻塞）

## Docker 部署方案 (推荐)

Phase 9.24: 提供完整的 Docker 部署示例，确保"默认安全"。

> 注意：
> - 仓库已内置 `frontend/backend/Dockerfile` 与根目录 `docker-compose.yml`（Phase 9.50）。
> - `nginx/` 示例目录仍为参考模板（可按下文示例自行添加/调整）。
### docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_USER: lncrna
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: lncrna_production
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./schema:/docker-entrypoint-initdb.d:ro
    networks:
      - backend

  # Redis 缓存
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks:
      - backend

  # FastAPI 后端
  backend:
    build:
      context: ./frontend/backend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      - ENV=production
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_USER=lncrna
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_NAME=lncrna_production
      - REDIS_HOST=redis
      - ADMIN_REQUIRE_API_KEY=true
      - ADMIN_API_KEY=${ADMIN_API_KEY}
      - TRUSTED_HOSTS=["your-domain.com"]
      - CORS_ORIGINS=["https://your-domain.com"]
      - GENOMES_DIR=/data/genomes
    volumes:
      - ./data/genomes:/data/genomes:ro
    depends_on:
      - postgres
      - redis
    networks:
      - backend

  # Nginx 反向代理（安全网关）
  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./frontend/web/dist:/var/www/html:ro
      - ./certs:/etc/nginx/certs:ro
    environment:
      - ADMIN_API_KEY=${ADMIN_API_KEY}  # 可选：仅在你使用 envsubst 模板渲染时需要
    depends_on:
      - backend
    networks:
      - backend
      - frontend

networks:
  backend:
    internal: true  # 后端网络不对外暴露
  frontend:

volumes:
  postgres_data:
```

### nginx/conf.d/default.conf

```nginx
upstream backend {
    server backend:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Admin 端点 - 服务端注入 Key + IP 白名单
    location /api/v1/admin {
        # 仅允许内网访问
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;

        # 服务端注入 Admin Key（前端无需配置）
        # 注意：Nginx 配置不原生支持读取环境变量为 $ADMIN_API_KEY；
        # 若要通过环境变量注入，请在容器启动时用 envsubst 渲染配置模板，
        # 或直接在配置文件中写入固定值并严格限制文件权限。
        proxy_set_header X-Admin-API-Key "your-secure-key-here";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_pass http://backend;
    }

    # 普通 API
    location /api/ {
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_pass http://backend;
    }

    # 健康检查（后端为根路径 /health，不在 /api/v1 下）
    location = /health {
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_pass http://backend;
    }

    # 前端静态文件
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;

        # 静态资源缓存
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

### 启动命令

```bash
# 1. 生成强密码
export DB_PASSWORD=$(openssl rand -hex 16)
export ADMIN_API_KEY=$(openssl rand -hex 32)

# 2. 保存到 .env 文件
cat > .env << EOF
DB_PASSWORD=${DB_PASSWORD}
ADMIN_API_KEY=${ADMIN_API_KEY}
EOF

# 3. 构建前端（不设置 VITE_ADMIN_API_KEY）
cd frontend/web
npm run build  # 注意：不要设置 VITE_ADMIN_API_KEY
cd ../..

# 4. 启动服务
docker-compose up -d

# 5. 验证
curl -k https://your-domain.com/health
```

### 安全注意事项

1. **`.env` 文件**：不要提交到版本控制，添加到 `.gitignore`
2. **Admin Key**：仅在 docker-compose.yml 和 Nginx 配置中使用
3. **前端构建**：确保 `VITE_ADMIN_API_KEY` 未设置
4. **网络隔离**：后端网络 (`backend`) 设置为 `internal: true`
5. **证书**：生产环境使用 Let's Encrypt 或商业证书

## 故障排查

### Admin API 返回 401

1. 检查 Nginx 是否正确注入 Header
2. 验证 `ADMIN_API_KEY` 在后端和 Nginx 中一致
3. 确认 IP 在白名单内

```bash
# 测试 Admin API
curl -X POST -H "X-Admin-API-Key: your-key" https://your-domain.com/api/v1/admin/mv-cache/reset
```

### CORS 错误

1. 确认 `CORS_ORIGINS` 包含完整 URL（含协议）
2. 检查浏览器控制台的具体错误信息

```bash
# 验证 CORS 配置
curl -I -H "Origin: https://your-domain.com" https://your-domain.com/health
```

### 数据库连接失败

1. 确认 Docker 网络正常
2. 检查 `DB_PASSWORD` 在 postgres 和 backend 中一致

```bash
# 检查容器日志
docker-compose logs backend
docker-compose logs postgres
```
