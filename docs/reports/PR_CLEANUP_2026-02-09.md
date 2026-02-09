# PR 清理审计记录（2026-02-09）

## 目标

- 清空 open PR：能合并就合并，不能合并就关闭
- 合并后尽量删除远端分支，保留可回滚路径

## 合并的 PR（按合并时间）

- #142 `chore(tracks): export chipseq by cell_line and document hg19 track regen`
  - mergedAt: 2026-02-09T04:34:12Z
  - mergeCommit: `f8471deec84222cced4ea38a5cea89d043b409e5`
- #141 `chore(deps-dev): bump the npm-development-minor-and-patch group across 1 directory with 12 updates`
  - mergedAt: 2026-02-09T04:36:34Z
  - mergeCommit: `d2a6f7fef838170075e9f3e04de156b30a342e73`
- #143 `chore(deps): bump axios from 1.13.4 to 1.13.5 in /frontend/web in the npm-production-minor-and-patch group`
  - mergedAt: 2026-02-09T04:37:14Z
  - mergeCommit: `bd2592db0295fac0d144724fd7020812f3d8bdc3`
- #144 `chore(deps): bump fastapi from 0.128.4 to 0.128.5 in /frontend/backend in the python-minor-and-patch group`
  - mergedAt: 2026-02-09T04:38:03Z
  - mergeCommit: `314d3c9c520a36ec41f3ecd512b44a3cb2ddc771`

## 关闭的 PR

- 无

## 分支与工作区清理

- 已移除 worktree：`.worktrees/roadmap-2026-02-09`
- 已删除远端分支：`roadmap/2026-02-09-next`（PR #142 合并后手动清理）
- 说明：本地可能仍残留同名分支；如需删除，可手动执行：`git branch -d roadmap/2026-02-09-next`

## 回滚指南（可回滚）

如需回滚某个 PR，推荐直接回滚其 merge commit：

```bash
git revert -m 1 <mergeCommit>
```

回滚后建议跑一次最小 CI 校验：

```bash
./scripts/run-tests.sh ci
```

