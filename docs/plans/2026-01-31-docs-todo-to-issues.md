# Docs TODO → GitHub Issues（2026-01-31）

> 本文档为“将文档中的下一步/待办转为可追踪 issue”的过程记录快照；现状以 `docs/CURRENT_STATUS.md` 为准。

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `docs/` 中的“下一步（1–2 周）/关键开放问题”落为 GitHub Issues（含验收标准与负责人），便于跟踪与回滚（issue 可关闭/可引用）。

**Architecture:** 优先以 `docs/CURRENT_STATUS.md` 的“下一步（1–2 周）”为权威输入；对历史快照中的 checkbox/计划清单不做“逐条建 issue”（避免把历史记录重新变成 backlog 噪音），仅在路线图中明确标注为未闭环的事项（例如 billing）单独建 issue。

**Tech Stack:** `gh` CLI、`rg`、Markdown。

---

## 执行记录

### 输入来源

- `docs/CURRENT_STATUS.md:69`（下一步 1–2 周）
- `docs/ROADMAP_2026-01-21.md:45`（GitHub-hosted Actions billing/额度风险条目）

### 快速扫描命令（用于盘点“可能造成误读”的信号）

> 仅用于发现候选点；是否建 issue 以 `docs/CURRENT_STATUS.md` 为准。

```bash
rg -n "(TODO|TBD|FIXME|待办)" docs
rg -n "\\[ \\]" docs --glob "*.md" --glob "!docs/testing/**"
```

---

## 已创建 Issues（可追踪入口）

- #87 `docs(ci): 补齐本地 CI 自举指引（Python 依赖/DB 可重复运行）`
- #88 `docs: 持续清理历史文档中易误读为 backlog 的信号`
- #89 `ci(perf): 固化性能门禁/回归锚点为稳定工作流（可审计可回滚）`
- #90 `ci: 排查并解除 GitHub-hosted Actions 因 billing/额度不启动`

---

## 参考

- `docs/CURRENT_STATUS.md:1`
- `docs/ROADMAP_2026-01-21.md:1`
- `docs/CI_SELF_HOSTED_RUNNER.md:1`
