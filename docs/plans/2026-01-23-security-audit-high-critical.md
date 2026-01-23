# Security Audit (High/Critical) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 修复依赖审计中 High/Critical 漏洞，保证 `pip-audit --strict` 与 `npm audit --audit-level=high` 通过。

**Architecture:** 先在隔离工作区执行审计并收集漏洞清单，再进行最小版本升级；Python 侧同步更新 `constraints.txt`，Node 侧更新 `package-lock.json`；最后补充必要的文档说明并验证。

**Tech Stack:** Python 3.11, pip-audit, npm audit, GitHub Actions

### Task 1: 运行安全审计并收集漏洞清单

**Files:**
- Modify: 无
- Test: `scripts/run-tests.sh`（security-audit 入口）

**Step 1: 运行后端安全审计（预期失败）**

Run: `bash scripts/run-tests.sh security-audit`
Expected: pip-audit 或 npm audit 报出 high/critical，记录漏洞包与版本要求。

**Step 2: 保存审计输出（人工记录）**

记录：包名、受影响版本、修复版本范围、Python/Node 侧分别列出。

**Step 3: 建立待升级清单**

输出：一个最小升级列表（避免大版本跳跃）。

### Task 2: Python 侧最小版本升级（高危）

**Files:**
- Modify: `frontend/backend/requirements.txt`
- Modify: `frontend/backend/constraints.txt`
- Test: `frontend/backend/tests/...`（由 smoke/ci 测试覆盖）

**Step 1: 写出失败的安全审计期望**

Run: `bash scripts/run-tests.sh security-audit`
Expected: pip-audit 仍失败（用于确认问题可复现）。

**Step 2: 更新 `requirements.txt` 或必要的上限/下限**

策略：仅提升触发漏洞的包版本范围，避免不必要的主版本升级。

**Step 3: 更新 `constraints.txt` 锁定解析版本**

方法：使用已有约束结构，手动更新涉及的包版本（保持注释结构）。

**Step 4: 重新运行 pip-audit**

Run: `cd frontend/backend && python -m pip_audit -r requirements.txt --strict --progress-spinner off`
Expected: pip-audit 通过。

### Task 3: Node 侧最小版本升级（高危）

**Files:**
- Modify: `frontend/web/package.json`
- Modify: `frontend/web/package-lock.json`

**Step 1: 运行 npm audit（预期失败）**

Run: `cd frontend/web && npm audit --registry=https://registry.npmjs.org --audit-level=high`
Expected: high/critical 报告。

**Step 2: 最小升级修复漏洞**

策略：优先 `npm audit fix`（不强制大版本）；如需手动升级，逐个提升受影响包。

**Step 3: 重新运行 npm audit**

Run: `cd frontend/web && npm audit --registry=https://registry.npmjs.org --audit-level=high`
Expected: npm audit 通过。

### Task 4: 文档与验证

**Files:**
- Modify: `SECURITY.md`（如需更新说明）
- Test: `bash scripts/run-tests.sh security-audit`
- Test: `bash scripts/run-tests.sh smoke`

**Step 1: 更新文档（如审计策略/命令变化）**

仅在命令或依赖策略变更时修改文档，保持信息一致。

**Step 2: 运行安全审计与 smoke**

Run: `bash scripts/run-tests.sh security-audit`
Run: `bash scripts/run-tests.sh smoke`
Expected: 全部通过。

**Step 3: 小步提交**

Commit 1: `chore(security): update python audit deps`

Commit 2: `chore(security): update npm audit deps`

Commit 3: `docs(security): sync audit guidance`（如有）
