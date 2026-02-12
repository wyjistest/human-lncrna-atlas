# Perf 门禁 + 公网访问可用性加固执行计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不牺牲安全性的前提下，提升“门禁稳定性 + 部署可用性”的排障效率：解决 `Invalid host header` 与“前端数据很小/全 0（baseline DB）”的高频误判。

**Architecture:**
- 后端 `/` 与 `/health` 暴露最小化运行元信息（`db_mode`/`db_name`），用于快速确认当前连接的数据库模式（production/baseline/custom）。
- 文档固化 FRP/NAT 公网访问命令与自检手册（`PUBLIC_HOST` + `PUBLIC_*_PORT` + curl 自检）。

**Tech Stack:** FastAPI / Pydantic / pytest / Bash

---

## Task 1：后端暴露 `db_mode/db_name`（含单测）

**Files:**
- Modify: `frontend/backend/main.py`
- Modify: `frontend/backend/app/schemas/common.py`
- Create: `frontend/backend/tests/test_root_health_db_meta_unit.py`

**Step 1: 写 failing tests（RED）**

目标断言：
- `read_root()` 返回 `db_mode/db_name`
- `health_check()` 返回的 `HealthResponse` 包含 `db_mode/db_name`

**Step 2: 运行测试确认失败（Verify RED）**

Run:
```bash
cd frontend/backend
pytest -q tests/test_root_health_db_meta_unit.py -m unit
```

Expected: 因缺少 `db_mode/db_name` 字段而失败。

**Step 3: 最小实现（GREEN）**
- `main.py`：为 `/` 与 `/health` 增加 `db_mode/db_name` 字段
- `common.py`：扩展 `HealthResponse` 模型新增字段

`db_mode` 判定规则（固定）：
- `DB_NAME == lncrna_production` → `production`
- `DB_NAME` 包含 `baseline`（忽略大小写）→ `baseline`
- 其它 → `custom`

**Step 4: 运行测试确认通过（Verify GREEN）**

Run:
```bash
cd frontend/backend
pytest -q tests/test_root_health_db_meta_unit.py -m unit
```

Expected: PASS。

---

## Task 2：文档固化 FRP/NAT 公网访问与自检

**Files:**
- Modify: `README.md`
- Modify: `docs/backend/DEPLOYMENT.md`

**Step 1: 增补 FRP/NAT 启动命令**
- 统一推荐从 repo root 使用：`PUBLIC_HOST=... PUBLIC_FRONTEND_PORT=... PUBLIC_BACKEND_PORT=... ./scripts/dev.sh`
- 明确 `Invalid host header` 的优先排查点：`PUBLIC_HOST` 是否正确 + 映射端口是否一致

**Step 2: 增补“快速自检”**

Run:
```bash
curl -s http://<public-ip-or-domain>:<public-backend-port>/ | python3 -m json.tool
curl -s http://<public-ip-or-domain>:<public-backend-port>/health | python3 -m json.tool
```

Expected: 能看到 `db_mode/db_name`（用于确认 production/baseline）。

---

## Task 3：全量门禁验证（本地）

Run:
```bash
bash scripts/run-tests.sh ci
```

Expected: exit 0。

---

## Task 4：提交与推送（可回滚）

约束：按主题拆分 commit，确保可 `git revert <sha>` 回滚。

