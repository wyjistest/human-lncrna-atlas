# Security Deployment Guide

Phase 9.16: 安全部署指南

## Admin API 认证

### 问题背景

`VITE_ADMIN_API_KEY` 通过前端构建注入，会嵌入到 JavaScript 产物中。任何能访问前端文件的用户都可以通过以下方式提取 Key：
- 浏览器开发者工具查看源码
- 下载 dist 文件并搜索 "X-Admin-API-Key"

### 部署场景与建议

| 场景 | 风险 | 推荐方案 |
|------|------|----------|
| 内网/VPN 部署 | 低 | 可使用 `VITE_ADMIN_API_KEY` |
| 公网部署 (CDN) | **高** | **禁止使用**，Key 会泄露 |
| 公网部署 (反代) | 中 | 由 Nginx 注入 Header |
| 公网部署 (完整) | 低 | 后端实现会话式认证 |

### 方案 1: 反向代理注入 (推荐)

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
