"""分析结果 API 路由

Phase 6.0-C: 为 Analysis Results 页面提供聚合统计数据

提供 4 个分析类型的综合摘要：
1. High Affinity - 高结合亲和力调控关系
2. Conservation - 跨物种保守性
3. Epigenetic - 表观遗传标记关联
4. Disease - 疾病基因网络

性能优化:
- 使用 Redis 缓存（TTL=1 小时）
- 复用现有查询逻辑
- 单次 API 调用获取所有摘要数据
"""
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error
from app.routers.chipseq_rate_limit import rate_limit
from app.core.cache import cache, CacheService
from app.schemas.analysis import (
    AnalysisSummaryResponse,
    HighAffinityAnalysis,
    ConservationAnalysis,
    EpigeneticAnalysis,
    DiseaseAnalysis,
    TopLncRNA,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/summary", response_model=AnalysisSummaryResponse)
@rate_limit("30/minute")
def get_analysis_summary(request: Request, db: Session = Depends(get_db)):
    """
    获取分析结果综合摘要（缓存 1 小时）

    **应用场景**:
    - Analysis Results 页面概览卡片
    - 数据分析仪表板
    - 科研项目摘要展示

    **返回内容**:
    1. **High Affinity**: 高结合亲和力统计（BA >= 100）
       - 总调控关系数、唯一 lncRNA/靶基因数
       - Top 20 lncRNA（按靶基因数排序）
       - 平均/最大 BA

    2. **Conservation**: 跨物种保守性统计
       - 4/3/2 物种保守的 lncRNA 数量

    3. **Epigenetic**: 表观遗传标记统计
       - 按组蛋白标记分组（H3K4me3, H3K27me3 等）
       - 按细胞类型分组（K562, GM12878 等）

    4. **Disease**: 疾病关联统计
       - 疾病数、关联 lncRNA 数、关联基因数

    **性能**: 缓存命中时 < 10ms，缓存未命中时 < 500ms
    """
    # 尝试从缓存获取
    cache_key = cache.make_key("analysis:summary")
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("[CACHE HIT] analysis:summary")
        return AnalysisSummaryResponse(**cached)

    logger.info("[CACHE MISS] analysis:summary - Computing statistics...")

    # ========================================================================
    # 1. High Affinity Analysis (BA >= 100)
    # ========================================================================
    high_affinity_sql = text("""
        WITH high_affinity_regs AS (
            SELECT
                r.regulation_id,
                r.lncrna_gene_id,
                r.target_gene_id,
                r.binding_affinity,
                lnc.gene_name as lncrna_name
            FROM regulations r
            JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
            WHERE r.binding_affinity >= 100
        )
        SELECT
            COUNT(*) as total_regulations,
            COUNT(DISTINCT lncrna_gene_id) as unique_lncrnas,
            COUNT(DISTINCT target_gene_id) as unique_targets,
            AVG(binding_affinity) as avg_ba,
            MAX(binding_affinity) as max_ba
        FROM high_affinity_regs
    """)

    try:
        ha_stats = db.execute(high_affinity_sql).fetchone()
    except Exception as e:
        raise sanitize_db_error(e, logger)

    # Top 20 lncRNAs by target count
    top_lncrnas_sql = text("""
        SELECT
            lnc.gene_name as lncrna_name,
            COUNT(DISTINCT r.target_gene_id) as target_count,
            AVG(r.binding_affinity) as avg_ba
        FROM regulations r
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        WHERE r.binding_affinity >= 100
        GROUP BY lnc.gene_name
        ORDER BY target_count DESC, avg_ba DESC
        LIMIT 20
    """)

    try:
        top_lncrnas_rows = db.execute(top_lncrnas_sql).fetchall()
    except Exception as e:
        raise sanitize_db_error(e, logger)

    top_lncrnas = [
        TopLncRNA(
            name=row.lncrna_name,
            target_count=row.target_count,
            avg_ba=round(float(row.avg_ba), 2)
        )
        for row in top_lncrnas_rows
    ]

    high_affinity = HighAffinityAnalysis(
        total_regulations=ha_stats.total_regulations or 0,
        unique_lncrnas=ha_stats.unique_lncrnas or 0,
        unique_targets=ha_stats.unique_targets or 0,
        avg_ba=round(float(ha_stats.avg_ba), 2) if ha_stats.avg_ba else 0.0,
        max_ba=round(float(ha_stats.max_ba), 2) if ha_stats.max_ba else 0.0,
        top_lncrnas=top_lncrnas
    )

    # ========================================================================
    # 2. Conservation Analysis
    # ========================================================================
    conservation_sql = text("""
        SELECT
            COUNT(DISTINCT CASE WHEN species_count = 4 THEN core_id END) as four_species,
            COUNT(DISTINCT CASE WHEN species_count = 3 THEN core_id END) as three_species,
            COUNT(DISTINCT CASE WHEN species_count = 2 THEN core_id END) as two_species
        FROM (
            SELECT
                g.core_id,
                COUNT(DISTINCT g.species_id) as species_count
            FROM genes g
            WHERE g.core_id IS NOT NULL
            GROUP BY g.core_id
            HAVING COUNT(DISTINCT g.species_id) >= 2
        ) AS conservation_counts
    """)

    try:
        cons_stats = db.execute(conservation_sql).fetchone()
    except Exception as e:
        raise sanitize_db_error(e, logger)

    conservation = ConservationAnalysis(
        four_species=cons_stats.four_species or 0,
        three_species=cons_stats.three_species or 0,
        two_species=cons_stats.two_species or 0,
        total_conserved=(cons_stats.four_species or 0) +
                        (cons_stats.three_species or 0) +
                        (cons_stats.two_species or 0)
    )

    # ========================================================================
    # 3. Epigenetic Analysis (ChIP-seq overlaps)
    # ========================================================================
    # Phase 9.13: 添加 MV 缺失时的降级处理，避免整页 500 错误
    # 与 /export/chipseq-overlaps 默认参数对齐：仅统计高置信度 (BA >= 100) 的重叠
    epigenetic_min_ba = 100.0
    epigenetic_sql = text("""
        SELECT
            COUNT(*) as total_overlaps,
            o.mark_name,
            o.mark_category,
            o.cell_type
        FROM mv_lncrna_chipseq_overlaps o
        WHERE o.binding_affinity >= :min_ba
        GROUP BY o.mark_name, o.mark_category, o.cell_type
    """)

    by_mark = {}
    by_cell_type = {}
    total_overlaps = 0
    bivalent_domains = 0
    active_marks = 0
    repressive_marks = 0

    try:
        epi_results = db.execute(epigenetic_sql, {"min_ba": epigenetic_min_ba}).fetchall()

        for row in epi_results:
            count = row.total_overlaps or 0
            total_overlaps += count

            # Aggregate by mark
            mark = row.mark_name
            by_mark[mark] = by_mark.get(mark, 0) + count

            # Aggregate by cell type
            cell = row.cell_type
            by_cell_type[cell] = by_cell_type.get(cell, 0) + count

            # Aggregate by mark category (for frontend stats cards)
            category = row.mark_category
            if category == "bivalent_component":
                bivalent_domains += count
            elif category == "activating":
                active_marks += count
            elif category == "repressive":
                repressive_marks += count

    except Exception as e:
        # MV 不存在或查询失败时，降级为空数据（不阻塞其他分析模块）
        logger.warning(
            f"[ANALYSIS] Epigenetic analysis failed (MV may not exist): {e}. "
            "Returning empty epigenetic data. "
            "Consider running: CREATE MATERIALIZED VIEW mv_lncrna_chipseq_overlaps ..."
        )
        # 保持默认的空值
        by_mark = {}
        by_cell_type = {}
        total_overlaps = 0
        bivalent_domains = 0
        active_marks = 0
        repressive_marks = 0

    epigenetic = EpigeneticAnalysis(
        total_overlaps=total_overlaps,
        by_mark=by_mark,
        by_cell_type=by_cell_type,
        bivalent_domains=bivalent_domains,
        active_marks=active_marks,
        repressive_marks=repressive_marks,
    )

    # ========================================================================
    # 4. Disease Analysis
    # ========================================================================
    avg_connections_sql = text("""
        SELECT AVG(connection_count) AS avg_connections
        FROM (
            SELECT
                trait_id,
                COUNT(DISTINCT core_id) AS connection_count
            FROM trait_gene_associations
            GROUP BY trait_id
        ) AS per_trait
    """)

    disease_sql = text("""
        SELECT
            COUNT(DISTINCT t.trait_id) as total_diseases,
            COUNT(DISTINCT cg.core_id) FILTER (WHERE cg.gene_type = 'lncRNA') as total_lncrnas,
            COUNT(DISTINCT cg.core_id) as total_genes
        FROM trait_gene_associations tga
        JOIN traits t ON tga.trait_id = t.trait_id
        JOIN core_genes cg ON tga.core_id = cg.core_id
    """)

    try:
        disease_stats = db.execute(disease_sql).fetchone()
        avg_connections_row = db.execute(avg_connections_sql).fetchone()
    except Exception as e:
        raise sanitize_db_error(e, logger)
    avg_connections = (
        float(avg_connections_row.avg_connections)
        if avg_connections_row and avg_connections_row.avg_connections is not None
        else 0.0
    )

    disease = DiseaseAnalysis(
        total_diseases=disease_stats.total_diseases or 0,
        total_lncrnas=disease_stats.total_lncrnas or 0,
        total_genes=disease_stats.total_genes or 0,
        avg_connections=avg_connections,
    )

    # ========================================================================
    # Build Response
    # ========================================================================
    result = AnalysisSummaryResponse(
        high_affinity=high_affinity,
        conservation=conservation,
        epigenetic=epigenetic,
        disease=disease
    )

    # 写入缓存（1 小时）
    cache.set(cache_key, result.model_dump(), CacheService.TTL_STATS)

    logger.info(f"[ANALYSIS] Summary computed: "
                f"HA={high_affinity.total_regulations}, "
                f"Conserved={conservation.total_conserved}, "
                f"Epi={epigenetic.total_overlaps}, "
                f"Diseases={disease.total_diseases}")

    return result
