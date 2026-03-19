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

补充 2：self-hosted 机器通常只有 1 个 runner 并行度；把 CI 拆成多个 job 反而会重复 checkout / install。  
因此 `Tests` workflow 在 **self-hosted + push(main)** 场景默认启用 `self-hosted-fast-ci`（把核心门禁合并到一个 job 内），以缩短总耗时。  
如果你需要逐 job 排障/手动启用可选 job，请使用 `workflow_dispatch` 手动触发（此时保留原多 job 结构）。

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

补充（常见坑）：
- 这两个 job 的 Postgres service **不会强制绑定宿主机 `5432`**（避免 runner 机器本地已有 Postgres/端口占用导致容器启动失败）。
- 如需排障实际端口，可查看 `${{ job.services.postgres.ports['5432'] }}`；本仓库 workflow 已将其写入 `DB_PORT`，无需手动改脚本。

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

⚠️ CORS 注意事项（非常常见的失败原因）：

- 该 job 会在 self-hosted runner 上启动 `vite preview` 作为前端入口，端口可能是 `5173..5192` 中的任意一个（取决于端口是否被占用）。
- 如果你的后端启动时设置了环境变量 `CORS_ORIGINS`（会覆盖后端默认值），必须包含实际的前端 origin（例如 `http://127.0.0.1:5173` / `http://127.0.0.1:5174` 等），否则浏览器会被 CORS 拦截，页面会显示 `Network error`，Playwright 也会失败。
- 推荐：不要把 `CORS_ORIGINS` 限死在单一端口；至少包含 `5173` 与 `5174`，或按需扩展到 `5173..5192`。

### 4.2) 推荐：每周全量回归（workflow_dispatch）

说明：push/main 在 self-hosted 上默认走 `self-hosted-fast-ci`（更快、更省 IO）；如果你想“更全”的回归覆盖，建议用 `workflow_dispatch` 手动触发一次 `Tests`，按需打开更重的 job（每周一次即可）。

#### 触发方式（GitHub UI）

1. 打开仓库 **Actions**
2. 选择 workflow：**Tests**
3. 点击右侧 **Run workflow**
4. 选择分支（建议 `main`），并按需填写 inputs（见下节“推荐组合”）

#### 推荐组合（inputs）

> 说明：这些 inputs 都只影响 `workflow_dispatch` 触发；**默认行为不变**（push/main 仍以 fast-ci 为主）。

- `runs_on=self-hosted`：强制跑在自托管 runner（可覆盖仓库变量 `CI_RUNS_ON`）
- `api_base_url=http://127.0.0.1:8000`：后端地址（用于 health check；同时会注入构建的 `VITE_API_BASE_URL`）
  - 如果你启用 `enable_e2e_tests` / `enable_performance_audit`：请确保该地址可访问且返回 `${API_BASE_URL}/health`
  - 推荐把后端跑在 runner 本机（更稳定、网络噪声更少）；也可指向远端后端（但可能引入波动）
- `enable_postgres_jobs=true`：启用需要 `services: postgres` 的 job（要求 runner 机器可用 Docker）
- `enable_e2e_tests=true`：启用集成向 E2E（Playwright；**需要可用后端服务**）
- `enable_performance_audit=true`：启用性能门禁（Playwright performance suite；**需要可用后端服务**）
- `enable_firefox_smoke=true`：额外跑一轮 Firefox smoke（仅 workflow_dispatch）

#### 触发方式（GH CLI，可复制）

最小“全量回归入口”（只切到 self-hosted，不额外打开重 job）：

```bash
gh workflow run Tests --ref main \
  -f runs_on=self-hosted \
  -f api_base_url=http://127.0.0.1:8000
```

更重的“每周全量回归”（按你机器能力选择；需要后端可用，Postgres jobs 还要求 Docker）：

```bash
gh workflow run Tests --ref main \
  -f runs_on=self-hosted \
  -f api_base_url=http://127.0.0.1:8000 \
  -f enable_postgres_jobs=true \
  -f enable_e2e_tests=true \
  -f enable_performance_audit=true \
  -f enable_firefox_smoke=true
```

触发后建议直接 watch（直到结束，失败返回非 0）：

```bash
run_id="$(gh run list --branch main --workflow Tests --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$run_id" --exit-status
```

### 4.3) 每周自动全量回归（schedule + 开关）

除上面的 `Tests` workflow 外，本仓库还提供一个“每周自动全量回归”workflow：

- 名称：`Weekly Regression (Self-hosted)`
- 文件：`.github/workflows/weekly-regression.yml`
- 内容（串行执行，便于排障/产物分离）：
  - `bash scripts/run-tests.sh ci-plus`
  - `MODE=check bash scripts/baselines/run_overlap_perf_regression_docker.sh`（Docker sample，自包含）
  - `MODE=check bash scripts/baselines/run_genes_regulations_perf_regression_docker.sh`（Docker sample，自包含）
- 时间：每周一 `02:00 UTC`（约等于北京时间周一 10:00）

⚠️ 为避免占用自托管机器资源，schedule **默认不执行**。如需开启，请在仓库变量里设置：

- `CI_ENABLE_WEEKLY_REGRESSION=true`

手动触发（不受上面开关影响）：

```bash
gh workflow run "Weekly Regression (Self-hosted)" --ref main
```

可选：覆盖 runner label（例如临时在 GitHub-hosted 上跑）：

```bash
gh workflow run "Weekly Regression (Self-hosted)" --ref main -f runs_on=ubuntu-latest
```

### 5) 如何验证是否生效

1. 触发方式（二选一）：
   - 推送到 `main` 分支：会自动触发 `Tests`；`Security Audit` 会在依赖清单变化时自动触发
   - 或在 GitHub UI 手动触发 workflow（`workflow_dispatch`）
2. 用 `gh` 查看运行状态：

```bash
gh run list --branch main --limit 5
```

若看到 `Tests` / `Security Audit` 能正常启动并执行 job，说明 self-hosted 止损方案已生效。

3. （可选）确认 job 确实跑在 self-hosted runner 上：

```bash
# 取最新一次 Tests 的 run_id（或直接从 run URL 里复制 ID）
gh run list --branch main --workflow Tests --limit 1

# 查看该 run 的 jobs 实际跑在谁身上（runner_name + labels）
# 说明：需要把 <OWNER>/<REPO> 与 <RUN_ID> 替换成真实值
gh api "/repos/<OWNER>/<REPO>/actions/runs/<RUN_ID>/jobs" \
  --jq '.jobs[] | {name,conclusion,runner_name,labels}'
```

当输出里 `labels` 包含 `self-hosted` 且 `runner_name` 有值时，说明该 job 正在 self-hosted runner 上执行。

4. `Self-hosted Fast CI` 的核心检查现会额外产出一组 `run-tests` 证据：
   - 在 GitHub Actions run 页面的 `Summary` 顶部会先显示 overview（`Result` / `Passed stages` / `Failed stages` / `First failed stage` / `First failed log`）
   - 随后会追加 Markdown summary，可直接查看各阶段 PASS/FAIL、耗时与提示
   - 同时会上传 `self-hosted-fast-ci-summary-<sha>` artifact，包含：
     - `run-tests-ci-summary.md`
     - `run-tests-ci-summary.json`
     - `run-tests-stage-logs/`
   - `run-tests-ci-summary.json` 顶层现固定包含 `schema_version`、`coverage`、`first_failed_stage`、`first_failed_log_relpath`
   - 若某阶段失败，优先按 `first_failed_log_relpath` 或 `first_failed_stage` 去对应的 `run-tests-stage-logs/<stage_id>.log` 排障

### 5.1) PR / Dependabot：为什么没有 checks？怎么验证？

出于安全考虑（self-hosted runner 不应默认执行 PR 的不受信任代码），本仓库的 `Tests` workflow 默认只对 `push(main)` 与 `workflow_dispatch` 触发（未启用 `pull_request`）。
因此你会看到：**PR 页面没有 CI checks**（包括 Dependabot PR）。

推荐工作流（可审计、可回滚）：

1. 直接 squash merge PR → 让 `push(main)` 的 `Tests` 在 self-hosted 上跑完（`self-hosted-fast-ci`）。
2. 若 `Tests` 失败：`git revert <merge_sha>` 回滚该次合并，再重新 push。

常用命令（按需）：

```bash
# 合并（squash）并删除远端分支（适合 Dependabot）
gh pr merge <PR_NUMBER> --squash --delete-branch

# 等待 main 的 CI 完成（从最新一次 Tests 开始 watch）
run_id="$(gh run list --branch main --workflow Tests --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$run_id" --exit-status
```

补充：如果你希望“尽量不要把不可构建状态合进 main”（尤其是依赖/锁文件变更、或 semver-major 升级），
推荐在 merge 前先在本地对 PR 分支跑一次最小 CI：

```bash
gh pr checkout <PR_NUMBER>
bash scripts/run-tests.sh ci
gh pr merge <PR_NUMBER> --squash --delete-branch
```

如你确实需要“合并前验证”，可以手动对 PR 分支触发一次 `workflow_dispatch`：

```bash
gh workflow run Tests --ref "<PR_BRANCH>"
```

### 6) 常见排障：Actions 下载失败（SSL / Proxy）

如果 self-hosted runner 偶发出现类似报错：

- `Failed to download action ... The SSL connection could not be established`

且你的机器环境变量里配置了 `http_proxy` / `https_proxy`（或 `HTTP_PROXY` / `HTTPS_PROXY`），可能导致 GitHub Actions Runner 的下载逻辑在某些代理实现下不稳定。

建议处理方式（择一即可）：
1. 让 runner 进程不要继承代理环境变量（例如在启动 runner 的脚本里 `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY`）。
2. 或为代理正确配置系统 CA / MITM 证书（取决于你的代理实现与安全策略）。

### 6.2) 常见排障：直连 GitHub 超时 / 不可达（需要代理）

如果你在 self-hosted 机器上发现直连 GitHub 超时（例如 `curl -I -m 8 https://github.com` 超时），可以先用“临时环境变量”的方式为 `gh`/`git` 增加代理（示例以本机代理端口 `7890` 为例）：

```bash
# 仅影响当前 shell/命令（推荐先这样验证）
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"

# 避免把本机服务（backend/health check 等）也走代理，导致卡住
export NO_PROXY="127.0.0.1,localhost,::1"
export no_proxy="127.0.0.1,localhost,::1"

# 验证：GitHub 200
curl -I -m 8 https://github.com | head

# 验证：gh 可用（示例）
gh run list --branch main --limit 5
```

注意：
- 如果你把代理写进 runner 的常驻环境（例如 systemd env），Actions runner 的“下载 action / checkout”也会继承代理；某些代理实现可能导致 SSL 下载不稳定（见上面的 6)）。
- 如你的环境必须依赖代理才能访问 GitHub，建议优先保证代理的 CA/证书链配置正确，或使用更稳定的网络路径。

### 6.1) 常见排障：actions/checkout 失败（git gnutls_handshake）

如果 self-hosted runner 偶发出现类似报错：

- `fatal: unable to access 'https://github.com/...': gnutls_handshake() failed: The TLS connection was non-properly terminated`

这是 git HTTPS 握手不稳定导致的 `actions/checkout` 偶发失败（和代码逻辑通常无关）。

本仓库的 `Tests` / `Security Audit` workflow 已做“止损”：

1. workflow 内对 git transport 做稳定性配置（HTTP/1.1 + TLSv1.2）。
2. 当 `actions/checkout` 仍失败时：自动通过 GitHub API 下载 `${repo}@${sha}` tarball 恢复源码继续执行。
   - 对需要 `.git` 的门禁（例如 gitleaks、docs drift check）：在 tarball 场景会额外初始化一个本地 git snapshot（用于 `git ls-files`）。

如果你仍频繁遇到 checkout 失败：
- 优先检查 runner 的代理/网络（见上面 6)）。
- 其次考虑把 runner 放在更稳定的网络环境，或为 git 配置更稳定的出口。

### 6.2) 常见排障：本机 git push/fetch 失败（网络/代理受限）

如果你在本机/自托管 runner 上遇到类似报错：

- `fatal: unable to access 'https://github.com/...': gnutls_handshake() failed`
- `Failed to connect to github.com port 443`

可以按以下优先级止损（推荐从上到下依次尝试）：

**A) 单次 git 命令显式走本机代理（保留原始 SHA，推荐）**

不建议把代理写进 `git config --global http.proxy/https.proxy`（容易影响 Actions runner 下载与 `actions/checkout`）。
优先使用“仅对单次命令生效”的方式：

```bash
# 如你本机代理端口为 7890（例如 Clash），可用这种方式只影响当前命令
http_proxy=http://localhost:7890 https_proxy=http://localhost:7890 git fetch --prune
http_proxy=http://localhost:7890 https_proxy=http://localhost:7890 git push
```

也可以使用仓库内置脚本（同样是“单次命令生效”，且会自动补齐 `NO_PROXY`，避免本机服务被误走代理）：

```bash
bash scripts/ci/git_with_proxy.sh fetch --prune
bash scripts/ci/git_with_proxy.sh push
```

**B) GitHub API 止损推送（不依赖 git 网络；会生成新 SHA）**

如果你确认 `gh api` 仍可正常访问 GitHub（`gh auth status` 显示已登录），可以使用本仓库提供的“止损推送”脚本：

```bash
# 可选：如果你之前配置过 git 全局代理（http.proxy/https.proxy），建议先移除，避免影响 runner/checkout 稳定性
git config --global --unset http.proxy
git config --global --unset https.proxy

# 以 GitHub API 的方式把本地 HEAD commit 追加到远端 main（不会 force）
python3 scripts/gh_push_commit.py --branch main --commit HEAD

# （可选）一次性推送多个 commits：先 dry-run 预览，再执行推送（按提交顺序逐个推送）
# 说明：range 不要求你能 git fetch 远端；但不支持 merge commit，建议先 rebase/squash 成线性历史。
# dry-run 会输出每个 commit 的变更文件列表，便于推送前人工复核（可审计/可回滚）。
python3 scripts/gh_push_commit.py --branch main --range "HEAD~3..HEAD" --dry-run
python3 scripts/gh_push_commit.py --branch main --range "HEAD~3..HEAD"
```

说明：
- 该脚本会把“本地 commit 引入的文件变更”重放到远端分支 HEAD 上，并创建一个新的远端 commit（SHA 与本地不相同，这是预期行为）。
- 默认带“远端覆盖护栏”：若远端同一路径在你本地父提交之后已发生变更，会中止推送，避免误覆盖。

---

## 本地止损（无需 Actions）

即使 Actions 被阻塞，也可以本地跑 CI 核心门禁（推荐 push 前先跑）：

```bash
bash scripts/run-tests.sh ci
```
