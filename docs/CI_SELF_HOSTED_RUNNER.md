# GitHub Actions：Self-hosted Runner 止损方案（账单/额度阻塞时）

当你看到 GitHub Actions 运行记录里的注释类似：

> The job was not started because recent account payments have failed or your spending limit needs to be increased

这通常意味着 **GitHub-hosted runner（例如 `ubuntu-latest`）被账单/额度（spending limit）阻塞**，workflow 直接无法启动，和代码本身无关。

本仓库提供两条解决路径（推荐顺序）：

## 方案 A（推荐）：修复 GitHub Billing / spending limit

在 GitHub 仓库或组织的 **Settings → Billing & plans** 修复支付/额度后，Actions 会恢复正常。

## 方案 B：启用 Self-hosted Runner（不消耗 GitHub Actions 分钟）

### 1) 添加 self-hosted runner

GitHub UI 路径：

1. 进入仓库：**Settings → Actions → Runners**
2. 点击 **New self-hosted runner**
3. 选择你的 OS/架构，按页面给出的命令在目标机器上完成安装与注册

建议：
- 选择一台长期在线的 Linux 机器（CI 稳定性更好）。
- runner 账号尽量使用最小权限用户，不建议用 root 常驻。
- 如果你在 root/sudo 下运行 `./config.sh` 看到 `Must not run with sudo`：请切换到普通用户执行（推荐）。确实要用 root 时可临时设置 `RUNNER_ALLOW_RUNASROOT=1`，但不建议（runner 将拥有 root 权限，风险更高）。

### 2) 配置仓库变量：让 workflow 跑在 self-hosted

GitHub UI 路径：

1. **Settings → Secrets and variables → Actions → Variables**
2. 新增变量：
   - `CI_RUNS_ON=self-hosted`

你也可以在手动触发 workflow 时，通过 `workflow_dispatch` 输入覆盖 runner（无需改仓库变量）：在触发页面填写 `runs_on=self-hosted`。

此后：
- `.github/workflows/test.yml` 与 `.github/workflows/security-audit.yml` 会默认在 self-hosted runner 上运行。
- 默认仍保持 `CI_RUNS_ON` 未配置时使用 `ubuntu-latest`（不破坏现有行为）。

补充：self-hosted runner 有持久磁盘缓存，因此 `Tests` workflow 在 self-hosted 上会禁用 `setup-node`/`setup-python` 的远端 cache（避免 artifact cache 下载/上传拖慢），依赖缓存由本机 `~/.npm` 与 pip cache 直接复用。

### 2.1) 资源建议（1 核 1G VPS 是否够）

结论：**1C1G 通常不够跑完整 `Tests` workflow**（尤其是 `npm ci`、前端 `build`、Playwright 安装/运行），很容易出现 OOM 或长时间排队。

更稳的建议：
- **最低建议**：2C / 4G（能比较稳定跑完一次 `Tests`）。
- **更推荐**：4C / 8G（依赖安装 + Playwright 更稳）。
- 如果只能用 1C1G：建议把 runner 用作“紧急止损”，仅跑 `Security Audit` 或最轻量的 job；并开启 swap（仍可能很慢）。

### 3) 可选：在 self-hosted 上启用 Postgres service 作业

`Tests` workflow 里有两个 job 使用了 `services: postgres`：
- `ETL E2E Smoke (Postgres)`
- `API Snapshot Baseline (Postgres)`

这些 job 在 self-hosted 上**默认跳过**（避免 Docker/权限差异导致 CI 直接失败）。

如果你的 self-hosted runner 机器已安装并可用 Docker（Actions Runner 用户有权限运行容器），可在仓库变量里额外设置：

- `CI_ENABLE_POSTGRES_JOBS=true`

或在手动触发 `Tests` workflow 时填写 `enable_postgres_jobs=true`（仅对 `workflow_dispatch` 生效）。

### 4) Playwright（e2e-smoke）在 self-hosted 的注意事项

`e2e-smoke` 在 GitHub-hosted runner 上使用 `npx playwright install chromium --with-deps` 自动安装系统依赖；
但在 self-hosted runner 上为避免 CI 里强行改系统环境，改为 `npx playwright install chromium`。

因此你需要在 runner 机器上**预先安装浏览器运行所需的系统依赖**（一次性操作）。

参考命令（在 runner 机器上执行）：

```bash
cd frontend/web
npx playwright install-deps chromium
```

### 4.1) 可选：E2E Tests (Playwright)

`E2E Tests (Playwright)` 是 self-hosted 的“集成向”E2E（会检查 backend 是否可用）。该 job 默认关闭；如需运行，在手动触发 `Tests` workflow 时填写 `enable_e2e_tests=true`，并可选通过 `api_base_url` 覆盖后端地址（默认 `http://127.0.0.1:8000`，健康检查为 `${API_BASE_URL}/health`）。

### 5) 如何验证是否生效

1. 触发方式（二选一）：
   - 推送到 `main` 分支：会自动触发 `Tests`；`Security Audit` 会在依赖清单变化时自动触发
   - 或在 GitHub UI 手动触发 workflow（`workflow_dispatch`）
2. 用 `gh` 查看运行状态：

```bash
gh run list --branch main --limit 5
```

若看到 `Tests` / `Security Audit` 能正常启动并执行 job，说明 self-hosted 止损方案已生效。

### 6) 常见排障：Actions 下载失败（SSL / Proxy）

如果 self-hosted runner 偶发出现类似报错：

- `Failed to download action ... The SSL connection could not be established`

且你的机器环境变量里配置了 `http_proxy` / `https_proxy`（或 `HTTP_PROXY` / `HTTPS_PROXY`），可能导致 GitHub Actions Runner 的下载逻辑在某些代理实现下不稳定。

建议处理方式（择一即可）：
1. 让 runner 进程不要继承代理环境变量（例如在启动 runner 的脚本里 `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY`）。
2. 或为代理正确配置系统 CA / MITM 证书（取决于你的代理实现与安全策略）。

---

## 本地止损（无需 Actions）

即使 Actions 被阻塞，也可以本地跑 CI 核心门禁（推荐 push 前先跑）：

```bash
bash scripts/run-tests.sh ci
```
