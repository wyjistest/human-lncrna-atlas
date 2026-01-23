# Docs TODO Cleanup Design

## 背景与目标

当前仓库中仍存在部分历史阶段文档（Phase 0/Phase 1/Session Summary）保留了“Mock/待办/未实现”描述，这会对新同学形成误导，尤其是 MSW 安装与 Mock 细节、导出功能的待办清单，以及早期 TODO 命名的会话总结。目标是将这些内容明确标注为“历史记录”，并指向当前实际实现与状态文档（`docs/CURRENT_STATUS.md`），避免把历史计划当作现状。

## 设计方案

采取“最小干预”的文档对齐策略：不删除历史内容，但在相关章节顶部添加更新说明，明确该段落为历史示例；将与 Mock/未实现相关的描述标注为“已废弃/历史”，避免误用。对于仍保留 TODO 的清单，将其改为“历史记录”或明确引用真实实现位置（例如 `frontend/web/src/utils/export.ts`），但不作功能层面的断言，避免出现不实声明。

## 影响范围与验证

仅修改 Markdown 文档，不改动任何代码逻辑。涉及文件主要集中在 `docs/phases/PHASE1_IMPLEMENTATION_PLAN.md`、`docs/phases/PHASE0_FOUNDATION.md` 与 `docs/sessions/SESSION_SUMMARY_2025-11-28_TODO_PHASE1-2.md`。验证方式保持轻量，使用 `python3 scripts/check_docs_commands.py` 做文档命令漂移检查，确保未引入错误启动命令或路径漂移。
