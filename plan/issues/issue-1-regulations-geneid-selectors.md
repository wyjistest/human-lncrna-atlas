# Issue Draft: feat(regulations) - gene_id selectors

## 背景

- 后端已提供 options 端点（含缓存）：
  - `GET /api/v1/regulations/lncrna-options`
  - `GET /api/v1/regulations/target-options`
- 目前前端 Regulations 筛选仍以 `lncrna_gene_name` / `target_gene_name` 模糊输入为主；可选增强是改为下拉选择器并以 `gene_id` 驱动筛选。

参考：
- `docs/api/REGULATIONS_API_SUMMARY.md`
- `frontend/web/src/api/regulations.ts`

## 目标

将 Regulations 页的 lncRNA/Target 筛选改为“选择器优先”的交互，并以 `gene_id` 作为主路径（更稳定、更可缓存、更易测试）。

## 范围（建议）

前端：
- `frontend/web/src/pages/Regulations/components/AdvancedFilters.tsx`
  - lncRNA / target 输入改为选择器（Select/AutoComplete）
  - 选择器数据源使用 `/regulations/*-options`
- `frontend/web/src/pages/Regulations/index.tsx`
  - 查询参数优先使用 `lncrna_gene_id` / `target_gene_id`（或现有约定的 id 参数）
  - 保持向后兼容：仍允许 name 参数存在，但 UI 默认走 id
- i18n：
  - `frontend/web/src/i18n/locales/zh-CN/regulations.json`
  - `frontend/web/src/i18n/locales/en-US/regulations.json`

不在范围：
- 不改动后端行为与响应结构（只消费现有端点）

## 验收标准

- 选择器可选择 lncRNA/target，筛选结果正确更新（无 400/500）
- 清空选择器后筛选回到“未限定”
- 不破坏现有 name-based 入口（如 URL/历史链接仍可工作）
- `cd frontend/web && npm run build` 通过

## 测试要求（配套 issue）

本 issue 只实现功能；测试覆盖由独立 issue 跟进（unit + mocked e2e-smoke）。

