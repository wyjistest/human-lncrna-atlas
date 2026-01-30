# Issue Draft: test(regulations) - selectors coverage

## 背景

Regulations 的 gene_id 选择器改造需要有可靠回归覆盖，避免：
- 选择器与 query params 漂移导致筛选无效
- UI 结构变更导致 E2E flaky

## 目标

为 “Regulations gene_id 选择器” 路径补齐：
- 前端单元测试（Vitest）
- Playwright mocked smoke（保持完全离线可跑：不依赖后端/DB）

## 范围（建议）

Vitest：
- 覆盖筛选参数拼装（选中/清空/边界）
- 覆盖选择器加载状态与错误态（mock API）

Playwright mocked smoke：
- 新增或扩展 `frontend/web/e2e/*regulations*` spec
- 以 `data-testid` 为主选择器（避免结构变更引发 strict mode 冲突）
- 通过 network interception 提供 options API 的 mock 响应

## 验收标准

- `bash scripts/run-tests.sh ci` 不回归（至少：相关 vitest + e2e-smoke 通过）
- `bash scripts/run-tests.sh e2e-smoke` 仍保持无需后端/DB 可跑
- 新增测试明确断言最小契约：选择器存在、选择后触发带 gene_id 的请求（或 URL 变化）

## 参考

- `docs/testing/e2e/README.md`
- `docs/CURRENT_STATUS.md`（以现状为准）

