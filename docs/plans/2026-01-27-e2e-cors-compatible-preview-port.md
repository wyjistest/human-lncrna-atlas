# E2E CORS-Compatible Preview Port Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 self-hosted 的集成 E2E（`E2E Tests (Playwright)`）在 preview 端口非 5173 时因后端 CORS 拒绝而导致页面 “Network error / Failed to load” 的问题，并让 workflow 能在端口被占用时给出可操作的 fail-fast 提示。

**Architecture:** 在 `.github/workflows/test.yml` 的 `e2e-tests` job 中，选择一个同时满足“端口可用”且“后端对该 Origin 返回 `Access-Control-Allow-Origin`”的 preview 端口；并在所有本地 `curl`（`127.0.0.1`/`localhost`）场景显式设置 `NO_PROXY`/`--noproxy`，避免 runner 继承代理环境变量导致误判。同步更新 self-hosted/E2E 文档，明确 `CORS_ORIGINS` 与 preview 端口的关系与推荐配置。

**Tech Stack:** GitHub Actions (YAML) / Bash / curl / Node.js / Playwright

---

### Task 1: 在 workflow 中选择 “CORS 兼容” 的 preview 端口

**Files:**
- Modify: `.github/workflows/test.yml`（`e2e-tests` job）

**Step 1: 让端口选择同时满足两个条件**

在 `Run E2E tests` step 中替换现有的 `PREVIEW_PORT` 选择逻辑：
1. 候选端口范围：`5173..5192`（与现有逻辑一致）
2. 条件 A：端口可绑定（避免与开发机/残留 preview 冲突）
3. 条件 B：对后端 `${API_BASE_URL}/health` 发起请求，并携带 `Origin: http://<PREVIEW_HOST>:<port>`，要求响应头包含 `access-control-allow-origin: <origin>`

若未找到满足条件的端口：fail-fast，并提示用户检查/扩展后端 `CORS_ORIGINS` 或释放占用端口。

**Step 2: 为本地地址请求增加 NO_PROXY**

对 workflow 内所有访问：
- `${API_BASE_URL}/health`
- `${BASE_URL}/`

的 `curl`，增加 `NO_PROXY=127.0.0.1,localhost,::1`（或 `curl --noproxy '*'`），避免 runner 继承代理环境变量导致 `curl` 走代理，从而出现“健康检查通过/失败不一致”的噪声。

**Step 3: 验证（GitHub Actions）**

Run:
- 触发 `workflow_dispatch`：
  - `runs_on=self-hosted`
  - `enable_e2e_tests=true`
  - `api_base_url=http://127.0.0.1:8000`

Expected:
- `E2E Tests (Playwright)` 不再因 preview 端口回退触发 CORS 问题；若后端 CORS 配置不匹配，应在端口选择阶段给出清晰错误提示并退出。

---

### Task 2: 更新 self-hosted/E2E 文档（CORS 与端口）

**Files:**
- Modify: `docs/CI_SELF_HOSTED_RUNNER.md`
- Modify: `docs/testing/e2e/README.md`

**Step 1: 增加“后端 CORS_ORIGINS 必须覆盖 preview origin”的说明**

说明要点：
- 集成 E2E 的前端是 `vite preview`（本机端口可能为 5173..5192），浏览器会发送 `Origin: http://127.0.0.1:<port>`
- 如果你在启动后端时设置了 `CORS_ORIGINS`（环境变量），必须包含对应 origin；否则浏览器会把请求当作 network error（Playwright 也会失败）
- 推荐：不要把 `CORS_ORIGINS` 限死在单一端口；或至少包含 5173 与 5174

---

### Task 3: 本机环境清理（非提交项）

**Step 1: 清理残留的 `vite preview` 进程**

目的：避免 5173 被残留预览服务占用，导致 workflow 必须回退端口。

Run:
- `ss -ltnp '( sport = :5173 )'`
- 如确认是残留 `vite preview`，终止对应进程

Expected:
- 5173 可用（或 workflow 能选到后端允许的端口）

