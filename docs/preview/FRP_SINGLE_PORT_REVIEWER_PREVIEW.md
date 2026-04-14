# FRP 单端口 Reviewer Preview

适用场景：

- 80/443 受限，公网只能通过 FRP 暴露高位端口
- 需要给 reviewer / 合作者一个稳定的公开 companion 入口
- 不希望再直接暴露 `vite dev server` 或独立后端端口

目标拓扑：

```text
公网 45.62.117.191:6003
  -> FRP
  -> 本机 127.0.0.1:6003 (本地反代)
     -> /            静态前端 dist
     -> /api         127.0.0.1:8010
     -> /health      127.0.0.1:8010
     -> /genomes     127.0.0.1:8010
```

## 约束

- reviewer 入口只保留一个公网端口：`6003`
- 不再给外部用户暴露 `6004`
- 前端必须使用 `npm run build` 的静态产物，不使用 `vite dev`
- 后端只监听 `127.0.0.1:8010`

## 1. 构建前端

```bash
cd frontend/web
npm ci
VITE_API_BASE_URL= npm run build
```

说明：

- `VITE_API_BASE_URL=` 强制前端在 production build 下走同源 `/api/v1/*`
- 构建产物输出到 `frontend/web/dist`

## 2. 启动后端

推荐使用单独环境变量启动 production-like preview：

```bash
cd frontend/backend

ENV=production \
ADMIN_REQUIRE_API_KEY=true \
ADMIN_API_KEY='<strong-random-key>' \
TRUSTED_HOSTS='["45.62.117.191","localhost","127.0.0.1"]' \
CORS_ORIGINS='["http://45.62.117.191:6003"]' \
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8010 --workers 1
```

说明：

- `TRUSTED_HOSTS` 必须包含公网 IP 或域名，否则反代后的请求会被拒绝
- `CORS_ORIGINS` 虽然在同源模式下基本不会命中，但仍建议显式配置成公开站点 origin
- 不要复用旧的 sample/baseline `8000` 进程

## 3. 启动本地反代

### 方案 A：仓库内置 preview server（当前机器推荐）

如果机器上没有系统级 `nginx`，直接使用仓库自带的单端口 preview server：

```bash
cd frontend/web
REVIEWER_PREVIEW_HOST=127.0.0.1 \
REVIEWER_PREVIEW_PORT=6003 \
REVIEWER_PREVIEW_API_TARGET=http://127.0.0.1:8010 \
npm run preview:reviewer
```

这个 server 会：

- 提供 `frontend/web/dist`
- 把 `/api`、`/health`、`/genomes` 代理到 `127.0.0.1:8010`
- 对 `/snapshot`、`/stats`、`/genes` 等子路由返回 `index.html`
- 让 reviewer 通过公共导航直接访问 `Submission Snapshot`

### 方案 B：Nginx

如果机器上已经有 Nginx，也可以继续使用仓库模板：

仓库提供模板：[reviewer-preview.conf](/data/wenyujianData/human-lncrna-atlas-github/nginx/reviewer-preview.conf)

关键点：

- 监听 `127.0.0.1:6003`
- `root` 指向 `frontend/web/dist`
- `/api`、`/health`、`/genomes` 代理到 `127.0.0.1:8010`
- `/` 使用 `try_files ... /index.html` 做 SPA fallback

## 4. FRP 转发

让 FRP 只转发一个端口：

```text
remote_port = 6003
local_ip     = 127.0.0.1
local_port   = 6003
```

不要再额外转发 `6004` 给 reviewer。

## 5. 验证

本机验证：

```bash
curl -sS http://127.0.0.1:8010/health
curl -sS 'http://127.0.0.1:8010/api/v1/genes?page=1&page_size=100' | python3 -m json.tool | head -40
curl -sS http://127.0.0.1:6003/ | head
curl -sS 'http://127.0.0.1:6003/api/v1/genes?page=1&page_size=100' | python3 -m json.tool | head -40
```

公网验证：

```bash
curl -sS http://45.62.117.191:6003/ | head
curl -sS 'http://45.62.117.191:6003/api/v1/genes?page=1&page_size=100' | python3 -m json.tool | head -40
```

浏览器验收重点：

- `/`、`/genes`、`/snapshot`、`/stats` 都能直接打开
- `Submission Snapshot` 页面能看到 freeze date 和 release commit
- 没有 `Failed to fetch dynamically imported module`
- 没有 CORS 错误
- 没有请求打到 `8000`、`8010` 或 `6004`

## 6. 排障要点

- 如果 `/genes` 又出现很小的数字，例如 `12` 条基因，说明代理仍打到了 baseline/sample 后端
- 如果首页能开但子路由刷新 404，说明 Nginx 没配 SPA fallback
- 如果接口在浏览器里 502/500，先检查 Nginx 实际代理目标是不是 `127.0.0.1:8010`
- 如果后端启动即失败，优先检查 `ADMIN_API_KEY`、`TRUSTED_HOSTS`、`CORS_ORIGINS`
