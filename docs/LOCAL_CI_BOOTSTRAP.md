# Local CI Bootstrap（本地 CI 自举）

> 目的：让你在新机器/新环境下，用尽量少的前置步骤，稳定跑通本仓库的本地 CI 门禁；并在失败时能快速定位问题。  
> 现状入口（唯一权威）：`docs/CURRENT_STATUS.md`

## 最短命令（推荐）

核心门禁（≈ GitHub Actions `Tests` 的核心检查集合）：

```bash
bash scripts/run-tests.sh ci
```

仅跑文档门禁（更快）：

```bash
bash scripts/run-tests.sh docs-check
```

如果你本机 `git push` 触发了 pre-push hook 并卡住，可先跳过一次（仍建议之后手动补跑）：

```bash
SKIP_LOCAL_CI=1 git push
```

## 最小依赖（推荐版本）

- Git
- Node.js：CI 使用 `20`（见 `.github/workflows/test.yml`）
- Python：CI 使用 `3.11`（见 `.github/workflows/test.yml`）
  - 需要支持 `python3 -m venv`（Ubuntu/Debian 常见是 `python3-venv` 包）
- 可选：Docker + docker compose
  - 仅在你要跑“需要 Postgres/Redis 的集成/基线/导入类脚本”时需要（`ci` 本身不需要）。

## 第一次跑通（推荐流程）

1. 在仓库根目录执行：

   ```bash
   bash scripts/run-tests.sh ci
   ```

2. 若你只想快速确认“文档没有漂移/误导信号”，可只跑：

   ```bash
   bash scripts/run-tests.sh docs-check
   ```

## 关键机制与可控开关（排障必看）

### 1) 后端 venv 自举（降低本地门槛）

`scripts/run-tests.sh` 在本地（非 `CI=true`）时会尝试自动创建 `frontend/backend/.venv`，并在依赖文件漂移时自动安装依赖（`requirements-dev.txt` + `constraints.txt`）。

可控开关：

- 禁用自举（你使用 Conda/pyenv/系统 Python，自行管理依赖）：

  ```bash
  SKIP_BACKEND_VENV_BOOTSTRAP=1 bash scripts/run-tests.sh ci
  ```

- 指定 Python 解释器（例如你的 Conda 环境）：

  ```bash
  BACKEND_PYTHON=/path/to/python bash scripts/run-tests.sh ci
  ```

### 2) pre-push hook（何时需要/如何跳过）

可选安装（会让 `git push` 自动跑本地门禁）：

```bash
bash scripts/install_git_hooks.sh
```

一次性跳过：

```bash
git push --no-verify
```

或用环境变量跳过（更显式、更可审计）：

```bash
SKIP_LOCAL_CI=1 git push
```

如需把 pre-push 默认门禁调轻/调重：

- 轻量：`LOCAL_CI_TARGET=smoke git push`
- 更接近 CI：`LOCAL_CI_TARGET=ci-plus git push`（会额外跑 Playwright mocked smoke）
- 最严格：`LOCAL_CI_TARGET=ci-full git push`（会追加依赖安全审计，可能受网络与漏洞影响）

### 3) 代理环境与 NO_PROXY（避免本地 health check 卡住）

脚本会默认设置：

- `NO_PROXY=127.0.0.1,localhost,::1`

目的是避免 `curl http://localhost:...` 意外走代理导致“命令卡住不动”。如你有更复杂的网络/内网域名需求，可在运行前自行覆盖 `NO_PROXY`。

## 数据库相关：何时需要 Postgres/Redis？

- `bash scripts/run-tests.sh ci`：不需要 Postgres/Redis（仅跑单测 + 语法/导入检查 + 文档门禁 + 迁移校验等）。
- 当你要跑需要真实服务/真实数据的测试或脚本时（例如后端 API 合同测试、部分性能/基线脚本），才需要：
  - 启动后端 + 数据库（本机或容器均可）
  - 并按对应文档设置必要的环境变量（例如 `ADMIN_API_KEY` 等）

一个“最小可复现”的容器路径（生产更接近，但需要你配置 `.env`）：

```bash
cp .env.example .env
# edit .env (DB_PASSWORD / ADMIN_API_KEY / TRUSTED_HOSTS / CORS_ORIGINS)
#
# 本机最小示例（仅用于本地开发/自测；不要提交到仓库）：
#   DB_PASSWORD=your-password
#   ADMIN_API_KEY=$(openssl rand -hex 32)
#   TRUSTED_HOSTS=["localhost","127.0.0.1"]
#   CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
# 如前端端口不是 5173，请把 CORS_ORIGINS 里的端口同步改成你的实际端口。
docker compose up -d
```

更多 self-hosted runner / billing 止损细节见：`docs/CI_SELF_HOSTED_RUNNER.md`。
