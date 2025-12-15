# 部署指南 - Human LncRNA Atlas Backend

**版本**: v0.1.0
**更新日期**: 2025-11-25

---

## 📋 目录

- [系统要求](#系统要求)
- [开发环境部署](#开发环境部署)
- [生产环境部署](#生产环境部署)
- [数据库配置](#数据库配置)
- [性能优化](#性能优化)
- [监控与日志](#监控与日志)

---

## 💻 系统要求

### 最低配置

- **CPU**: 2核
- **内存**: 4GB
- **磁盘**: 20GB
- **操作系统**: Linux (Ubuntu 20.04+) / macOS

### 推荐配置（生产环境）

- **CPU**: 4核+
- **内存**: 8GB+
- **磁盘**: 50GB+ SSD
- **操作系统**: Ubuntu 22.04 LTS

### 软件依赖

- Python 3.11+
- PostgreSQL 14+
- pip 23+

---

## 🚀 开发环境部署

### 1. 克隆项目

```bash
cd /data/wenyujianData/humanLncAtlas/frontend/backend
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

创建 `.env` 文件：

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=lncrna_production
DB_USER=amax
DB_PASSWORD=your_password

# 应用配置
APP_NAME="Human LncRNA Atlas API"
APP_VERSION=0.1.0
LOG_LEVEL=INFO

# CORS配置（开发环境）
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### 5. 验证数据库连接

```bash
psql -U amax -h localhost -d lncrna_production -c "SELECT COUNT(*) FROM genes;"
```

应返回: `17248`

### 6. 启动开发服务器

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 7. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# API文档
open http://localhost:8000/docs
```

---

## 🏭 生产环境部署

### 方案1: Systemd服务（推荐）

#### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/lncrna-api.service
```

内容：

```ini
[Unit]
Description=Human LncRNA Atlas API
After=network.target postgresql.service

[Service]
Type=simple
User=amax
WorkingDirectory=/data/wenyujianData/humanLncAtlas/frontend/backend
Environment="PATH=/data/wenyujianData/humanLncAtlas/frontend/backend/venv/bin"
ExecStart=/data/wenyujianData/humanLncAtlas/frontend/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable lncrna-api
sudo systemctl start lncrna-api
sudo systemctl status lncrna-api
```

#### 3. 查看日志

```bash
sudo journalctl -u lncrna-api -f
```

---

### 方案2: Docker部署

#### 1. 创建 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 2. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_NAME=lncrna_production
      - DB_USER=amax
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      - db
    restart: always

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=lncrna_production
      - POSTGRES_USER=amax
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

volumes:
  postgres_data:
```

#### 3. 启动容器

```bash
docker-compose up -d
docker-compose logs -f api
```

---

### 方案3: Nginx反向代理

#### 1. 安装Nginx

```bash
sudo apt install nginx
```

#### 2. 配置Nginx

```bash
sudo nano /etc/nginx/sites-available/lncrna-api
```

内容：

```nginx
server {
    listen 80;
    server_name api.lncrna-atlas.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 静态文件缓存
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_cache_valid 200 1h;
    }
}
```

#### 3. 启用配置

```bash
sudo ln -s /etc/nginx/sites-available/lncrna-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🗄️ 数据库配置

### 性能优化配置

编辑 `/etc/postgresql/14/main/postgresql.conf`:

```ini
# 内存配置（8GB服务器）
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 32MB

# 连接配置
max_connections = 100

# 查询优化
random_page_cost = 1.1  # SSD
effective_io_concurrency = 200

# WAL配置
wal_buffers = 16MB
checkpoint_completion_target = 0.9
```

### 建议的索引

```sql
-- 已有的主键和外键索引

-- 性能优化索引（如果查询慢）
CREATE INDEX IF NOT EXISTS idx_regulations_species_id ON regulations(species_id);
CREATE INDEX IF NOT EXISTS idx_regulations_lncrna_gene_id ON regulations(lncrna_gene_id);
CREATE INDEX IF NOT EXISTS idx_regulations_target_gene_id ON regulations(target_gene_id);
CREATE INDEX IF NOT EXISTS idx_regulations_binding_affinity ON regulations(binding_affinity);

CREATE INDEX IF NOT EXISTS idx_genes_species_id ON genes(species_id);
CREATE INDEX IF NOT EXISTS idx_genes_core_id ON genes(core_id);
CREATE INDEX IF NOT EXISTS idx_genes_gene_name ON genes(gene_name);
```

### 数据库备份

```bash
# 每日备份脚本
#!/bin/bash
BACKUP_DIR="/backup/lncrna"
DATE=$(date +%Y%m%d_%H%M%S)

pg_dump -U amax -h localhost lncrna_production | gzip > $BACKUP_DIR/lncrna_$DATE.sql.gz

# 保留最近7天的备份
find $BACKUP_DIR -name "lncrna_*.sql.gz" -mtime +7 -delete
```

---

## ⚡ 性能优化

### 1. Uvicorn Workers配置

```bash
# 根据CPU核心数设置workers
# 推荐: workers = (2 × CPU核心数) + 1

# 4核服务器
uvicorn main:app --workers 9 --host 0.0.0.0 --port 8000

# 8核服务器
uvicorn main:app --workers 17 --host 0.0.0.0 --port 8000
```

### 2. 数据库连接池

当前使用 `NullPool`（无连接池），生产环境可改为：

```python
# app/core/database.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=20,          # 连接池大小
    max_overflow=10,       # 最大溢出连接
    pool_pre_ping=True,
    echo=False,
)
```

### 3. Redis缓存（可选）

安装Redis：

```bash
sudo apt install redis-server
```

配置缓存：

```python
# app/core/cache.py
import redis
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(expire=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, expire, json.dumps(result))
            return result
        return wrapper
    return decorator
```

---

## 📊 监控与日志

### 1. 应用日志

配置日志文件：

```python
# main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/lncrna-api/app.log'),
        logging.StreamHandler()
    ]
)
```

### 2. 访问日志

Nginx访问日志：

```bash
tail -f /var/log/nginx/access.log
```

### 3. 性能监控

使用 Prometheus + Grafana：

```bash
# 安装 prometheus-fastapi-instrumentator
pip install prometheus-fastapi-instrumentator

# main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

访问指标: `http://localhost:8000/metrics`

### 4. 健康检查脚本

```bash
#!/bin/bash
# /usr/local/bin/check-api-health.sh

HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "✅ API健康"
    exit 0
else
    echo "❌ API异常 (HTTP $RESPONSE)"
    # 发送告警
    exit 1
fi
```

定时检查（crontab）：

```bash
*/5 * * * * /usr/local/bin/check-api-health.sh
```

---

## 🔒 安全配置

### 1. 防火墙配置

```bash
# 只允许特定IP访问
sudo ufw allow from 192.168.1.0/24 to any port 8000

# 或使用Nginx反向代理，不直接暴露8000端口
sudo ufw deny 8000
sudo ufw allow 80
sudo ufw allow 443
```

### 2. HTTPS配置（Let's Encrypt）

```bash
# 安装certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d api.lncrna-atlas.com

# 自动续期
sudo certbot renew --dry-run
```

### 3. 环境变量安全

```bash
# 不要将 .env 提交到git
echo ".env" >> .gitignore

# 生产环境使用环境变量
export DB_PASSWORD="strong_password_here"
```

---

## 🧪 测试部署

### 运行测试套件

```bash
# 集成测试
pytest tests/test_api_smoke.py -v

# 性能测试
pytest tests/test_performance.py -v -s

# 所有测试
pytest tests/ -v
```

### 预期结果

- ✅ 13个集成测试全部通过
- ✅ 7个性能测试全部通过
- ✅ 响应时间<1秒（1000条数据）

---

## 📝 部署检查清单

### 部署前

- [ ] 数据库备份完成
- [ ] 环境变量配置正确
- [ ] 依赖包版本锁定（requirements.txt）
- [ ] 测试套件全部通过
- [ ] 性能测试达标

### 部署后

- [ ] 健康检查通过 (`/health`)
- [ ] API文档可访问 (`/docs`)
- [ ] 核心端点测试通过
- [ ] 日志正常输出
- [ ] 监控指标正常

### 生产环境

- [ ] HTTPS配置完成
- [ ] 防火墙规则配置
- [ ] 数据库备份计划
- [ ] 监控告警配置
- [ ] 负载均衡配置（如需要）

---

## 🆘 故障排查

### 问题1: 数据库连接失败

```bash
# 检查数据库状态
sudo systemctl status postgresql

# 检查连接
psql -U amax -h localhost -d lncrna_production

# 查看日志
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### 问题2: API响应慢

```bash
# 检查数据库查询
# 启用 echo=True 查看SQL

# 检查系统资源
htop
iostat -x 1

# 检查数据库连接数
psql -U amax -c "SELECT count(*) FROM pg_stat_activity;"
```

### 问题3: 服务无法启动

```bash
# 查看服务日志
sudo journalctl -u lncrna-api -n 50

# 检查端口占用
lsof -i :8000

# 手动启动测试
cd /data/wenyujianData/humanLncAtlas/frontend/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 📚 相关文档

- [API使用指南](./API_GUIDE.md)
- [会话总结](../../SESSION_SUMMARY_2025-11-25.md)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [PostgreSQL文档](https://www.postgresql.org/docs/)

---

**最后更新**: 2025-11-25
**维护者**: Human LncRNA Atlas Team
