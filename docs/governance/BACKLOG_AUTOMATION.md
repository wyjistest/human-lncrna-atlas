# Backlog Automation

本页说明仓库当前的 backlog 治理规则，以及“事实 / 路线图 / 待办”分别应该去哪里看。

## 单一事实源

- 当前事实：`docs/CURRENT_STATUS.md`
- 当前路线图：`docs/roadmaps/ROADMAP_CURRENT.md`
- backlog 源文件：`.github/governance/backlog.yml`
- backlog issue：由 `governance-sync` workflow 自动创建/更新/关闭

## 使用规则

1. 想更新“当前实现/当前数据覆盖/当前 CI 状态”时，改 `docs/CURRENT_STATUS.md`
2. 想更新“接下来做什么、优先级是什么”时，改 `.github/governance/backlog.yml`
3. 想知道当前 backlog 在 GitHub 上长什么样，查看带 `<!-- backlog-id: ... -->` marker 的 managed issues
4. 不要把新的 checklist backlog 再写回 `docs/CURRENT_STATUS.md`

## 自动化行为

同步脚本：

```bash
python3 scripts/governance/sync_backlog_issues.py \
  --repo "wyjistest/human-lncrna-atlas" \
  --dry-run
```

默认行为：

- 自动补齐缺失的 labels
- 自动补齐缺失的 milestone（默认：`Current Roadmap`）
- 依据 `backlog-id` 创建或更新 issue
- manifest 删除或 `state: closed` 时，自动关闭对应 issue

## Manifest 约定

`.github/governance/backlog.yml` 当前采用 **JSON-compatible YAML**：

- 好处：标准库可直接解析，无需额外依赖
- 约束：每个 item 至少包含 `id`、`title`、`labels`、`acceptance_criteria`、`state`

推荐字段：

- `id`
- `title`
- `summary`
- `labels`
- `milestone`
- `priority`
- `body_sections`
- `acceptance_criteria`
- `state`

说明：

- `id`、`title`、`labels`、`acceptance_criteria`、`state` 是最小必填字段
- `summary`、`priority`、`body_sections` 等推荐字段属于增强信息；未提供时，同步脚本会省略对应正文片段，而不是报错

## 人工新增 issue 的规则

如果只是临时讨论或一次性追踪，可以手工创建普通 issue。

如果该事项属于当前正式 backlog，请优先修改 `.github/governance/backlog.yml`，再让同步脚本/工作流生成 issue，而不是手工创建一个无法回写的 issue。
