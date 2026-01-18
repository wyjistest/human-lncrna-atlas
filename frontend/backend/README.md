# Human LncRNA Atlas - Backend API

跨物种lncRNA调控网络数据库的FastAPI后端服务。

## 快速开始

### 1. 安装依赖

推荐使用 venv/venv，并按用途安装依赖：

```bash
# 如果使用虚拟环境
source venv/bin/activate

# 运行服务（仅运行时依赖）
python3 -m pip install -r requirements.txt -c constraints.txt

# 开发/测试（包含 pytest/ruff 等）
python3 -m pip install -r requirements-dev.txt -c constraints.txt

# 验证依赖
python3 -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
python3 -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__}')"
```

### 2. 配置环境变量

```bash
# 复制配置示例
cp .env.example .env

# 编辑配置（可选，默认配置已可用）
nano .env
```

### 3. 启动服务

```bash
# 方式1: 使用 uvicorn 启动（推荐）
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方式2: 使用Python运行
python3 main.py
```

### 4. 访问API文档

服务启动后，访问以下URL：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health

## API端点概览

### 基因相关 (`/api/v1/genes`)

- `GET /api/v1/genes` - 获取基因列表（分页、过滤）
- `GET /api/v1/genes/{gene_id}` - 获取基因详情
- `GET /api/v1/genes/{gene_id}/orthologs` - 获取直系同源基因

### 调控关系 (`/api/v1/regulations`)

- `GET /api/v1/regulations` - 获取调控关系列表
- `GET /api/v1/regulations/{regulation_id}` - 获取调控详情
- `GET /api/v1/regulations/gene/{gene_id}` - 获取基因的调控关系

### 疾病关联 (`/api/v1/diseases`)

- `GET /api/v1/diseases` - 获取疾病列表
- `GET /api/v1/diseases/{trait_id}` - 获取疾病详情
- `GET /api/v1/diseases/{trait_id}/genes` - 获取疾病关联基因
- `GET /api/v1/diseases/gene/{gene_id}/associations` - 获取基因的疾病关联

### 统计分析 (`/api/v1/stats`)

- `GET /api/v1/stats/overview` - 全局统计概览
- `GET /api/v1/stats/top-genes` - Top基因（按调控数量）
- `GET /api/v1/stats/top-diseases` - Top疾病（按关联基因数）
- `GET /api/v1/stats/conserved-regulations` - 保守调控关系

### 网络分析 (`/api/v1/network`)

- `GET /api/v1/network/gene/{gene_id}` - 获取基因调控网络数据
- `GET /api/v1/network/compare` - 跨物种网络对比

### Admin 运维 (`/api/v1/admin`)

> ⚠️ SECURITY：生产环境强烈建议启用 `ADMIN_REQUIRE_API_KEY=true`，并通过 `X-Admin-API-Key` 访问。

- `GET /api/v1/admin/health` - 系统健康与资源指标（依赖 `psutil`）
- `GET /api/v1/admin/cache/stats` - 缓存统计（命中率 + namespaces/keys top + compute 耗时）
- `POST /api/v1/admin/cache/invalidate/{namespace}` - 使指定缓存命名空间失效（白名单）
- `GET /api/v1/admin/materialized-views/status` - 查询物化视图状态与刷新锁状态
- `POST /api/v1/admin/materialized-views/refresh` - 刷新物化视图（支持 CONCURRENTLY / 超时配置）

## 数据库连接

默认连接配置：

```
Host: localhost
Port: 5432
User: amax
Database: lncrna_production
Password: （从~/.pgpass读取）
```

## 项目结构

```
backend/
├── main.py                 # FastAPI应用入口
├── requirements.txt        # Python依赖
├── requirements-dev.txt    # 开发/测试依赖
├── .env.example           # 配置示例
├── app/
│   ├── __init__.py
│   ├── core/              # 核心配置
│   │   ├── config.py      # 应用配置
│   │   └── database.py    # 数据库连接
│   ├── models/            # SQLAlchemy ORM模型
│   │   └── models.py
│   ├── schemas/           # Pydantic数据模型
│   │   ├── common.py
│   │   ├── gene.py
│   │   ├── regulation.py
│   │   ├── disease.py
│   │   └── stats.py
│   └── routers/           # API路由
│       ├── genes.py
│       ├── regulations.py
│       ├── diseases.py
│       ├── stats.py
│       └── network.py
└── venv/                  # 虚拟环境（可选）
```

## 开发提示

### 运行测试

```bash
# 测试数据库连接
python3 -c "from app.core.database import init_db; init_db()"

# 测试API健康检查
curl http://localhost:8000/health
```

### 刷新物化视图（可选，提升部分端点 cache-miss 性能）

推荐生产环境使用脚本定时刷新（例如 cron/ systemd timer）：

```bash
./scripts/refresh_materialized_views.sh
```

也可使用 Admin API 触发（需要 `X-Admin-API-Key`）：

```bash
curl -H "X-Admin-API-Key: <ADMIN_API_KEY>" "http://localhost:8000/api/v1/admin/materialized-views/status"
curl -X POST -H "X-Admin-API-Key: <ADMIN_API_KEY>" -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/admin/materialized-views/refresh" \
  -d '{"concurrently": true, "timeout_seconds": 600}'
```

### 查看日志

```bash
# 启动时会显示详细日志
python3 -m uvicorn main:app --log-level debug
```

### 生产环境请求日志调优（建议）

默认会记录所有请求（`REQUEST_LOG_SLOW_THRESHOLD_MS=0` 且 `REQUEST_LOG_SAMPLE_RATE=1.0`）。在高 QPS 场景建议通过环境变量降低日志 I/O 压力：

- `REQUEST_LOG_SLOW_THRESHOLD_MS=200`：仅记录慢请求（按需调整阈值）
- `REQUEST_LOG_SAMPLE_RATE=0.1`：采样率 10%（按需调整）
- `REQUEST_LOG_MAX_URL_LENGTH=2048`：限制 URL 长度，避免超长查询字符串导致日志膨胀
- 如无需请求日志：`REQUEST_LOG_ENABLED=false`

配置示例见 `frontend/backend/.env.example`（已包含上述选项的注释说明）。

### 生产部署

```bash
# 使用多worker模式
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 或使用gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 故障排查

### 数据库连接失败

1. 检查PostgreSQL服务：`systemctl status postgresql`
2. 检查数据库是否存在：`psql -U amax -l`
3. 检查~/.pgpass文件权限：`chmod 600 ~/.pgpass`

### 端口占用

```bash
# 检查端口占用
lsof -i :8000

# 使用其他端口
python3 -m uvicorn main:app --port 8001
```

## 技术栈

- **FastAPI** >=0.118.0 - 现代Web框架（StreamingResponse 生命周期修复 + 安全修复）
- **SQLAlchemy** 2.0.23 - ORM
- **Pydantic** >=2.5.0 - 数据验证
- **Uvicorn** >=0.30.0 - ASGI服务器
- **PostgreSQL** 15+ - 数据库（依赖 NULLS NOT DISTINCT 等特性）

## API版本

- **当前版本**: v0.1.0
- **API前缀**: /api/v1

## 许可证

此项目用于学术研究。
