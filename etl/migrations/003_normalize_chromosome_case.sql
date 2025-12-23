-- ============================================================================
-- 迁移脚本: 染色体字段大小写规范化
-- Phase 9.20 - Codex 审查修复
-- ============================================================================
-- 问题: ETL 直接写入原始 Best_Peak_Chr 值，API 查询时使用 .lower()
--       导致大小写不一致时查询不到数据
-- 解决: 统一所有染色体字段为小写
-- ============================================================================

-- 预估影响行数
SELECT
    'target_chromosome 需规范化' as field,
    COUNT(*) as affected_rows
FROM regulations
WHERE target_chromosome IS NOT NULL
  AND target_chromosome != LOWER(target_chromosome);

SELECT
    'best_peak_chr 需规范化' as field,
    COUNT(*) as affected_rows
FROM regulations
WHERE best_peak_chr IS NOT NULL
  AND best_peak_chr != LOWER(best_peak_chr);

-- 开始迁移
BEGIN;

-- 更新 target_chromosome
UPDATE regulations
SET target_chromosome = LOWER(target_chromosome)
WHERE target_chromosome IS NOT NULL
  AND target_chromosome != LOWER(target_chromosome);

-- 更新 best_peak_chr
UPDATE regulations
SET best_peak_chr = LOWER(best_peak_chr)
WHERE best_peak_chr IS NOT NULL
  AND best_peak_chr != LOWER(best_peak_chr);

COMMIT;

-- 验证
SELECT
    'target_chromosome 规范化后' as field,
    COUNT(*) as remaining_mixed_case
FROM regulations
WHERE target_chromosome IS NOT NULL
  AND target_chromosome != LOWER(target_chromosome);

SELECT
    'best_peak_chr 规范化后' as field,
    COUNT(*) as remaining_mixed_case
FROM regulations
WHERE best_peak_chr IS NOT NULL
  AND best_peak_chr != LOWER(best_peak_chr);

-- ============================================================================
-- 执行方式:
--   psql -d lncrna_production -f etl/migrations/003_normalize_chromosome_case.sql
-- ============================================================================
