# Security Deployment Guide

Phase 9.24: 安全部署指南（Codex 审查增强版 + Docker 支持）

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

- [ ] `VITE_ADMIN_API_KEY` 在公网部署时未设置
- [ ] 使用反向代理注入 Admin Key 或实现会话认证
- [ ] `GENOMES_DIR` 指向专用目录，无敏感文件
- [ ] `CORS_ORIGINS` 仅包含实际前端域名
- [ ] Admin 端点有 IP 白名单或二次认证

## Docker 部署方案 (推荐)

Phase 9.24: 提供完整的 Docker 部署示例，确保"默认安全"。

> 注意：当前仓库未内置 `frontend/backend/Dockerfile` 与 `nginx/` 示例目录，下面为参考模板。
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
