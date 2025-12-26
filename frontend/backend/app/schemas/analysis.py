"""分析结果 API Schema 定义

Phase 6.0-C: 为 Analysis Results 页面提供聚合统计数据
"""
from typing import List, Dict
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# High Affinity Analysis Schemas
# ============================================================================

class TopLncRNA(BaseModel):
    """Top lncRNA 模型"""

    name: str = Field(description="lncRNA 名称")
    target_count: int = Field(description="靶基因数量")
    avg_ba: float = Field(description="平均结合亲和力")

    model_config = ConfigDict(from_attributes=True)


class HighAffinityAnalysis(BaseModel):
    """高亲和力分析统计"""

    total_regulations: int = Field(description="总调控关系数")
    unique_lncrnas: int = Field(description="唯一 lncRNA 数量")
    unique_targets: int = Field(description="唯一靶基因数量")
    avg_ba: float = Field(description="平均结合亲和力")
    max_ba: float = Field(description="最大结合亲和力")
    top_lncrnas: List[TopLncRNA] = Field(description="Top 20 lncRNA（按靶基因数）")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Conservation Analysis Schemas
# ============================================================================

class ConservationAnalysis(BaseModel):
    """保守性分析统计"""

    four_species: int = Field(description="4 物种保守的 lncRNA 数")
    three_species: int = Field(description="3 物种保守的 lncRNA 数")
    two_species: int = Field(description="2 物种保守的 lncRNA 数")
    total_conserved: int = Field(description="保守 lncRNA 总数")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Epigenetic Analysis Schemas
# ============================================================================

class EpigeneticAnalysis(BaseModel):
    """表观遗传分析统计"""

    total_overlaps: int = Field(description="总重叠数")
    by_mark: Dict[str, int] = Field(description="按组蛋白标记分组统计")
    by_cell_type: Dict[str, int] = Field(description="按细胞类型分组统计")
    # Phase 9.29+：补齐前端统计卡片所需字段（向后兼容，提供默认值）
    bivalent_domains: int = Field(default=0, description="Bivalent domains 重叠数（按 mark_category=bivalent_component 汇总）")
    active_marks: int = Field(default=0, description="活跃标记重叠数（按 mark_category=activating 汇总）")
    repressive_marks: int = Field(default=0, description="抑制标记重叠数（按 mark_category=repressive 汇总）")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Disease Analysis Schemas
# ============================================================================

class DiseaseAnalysis(BaseModel):
    """疾病关联分析统计"""

    total_diseases: int = Field(description="总疾病数")
    total_lncrnas: int = Field(description="关联的 lncRNA 总数")
    total_genes: int = Field(description="关联的基因总数")
    # Phase 9.29+：补齐前端统计卡片所需字段（向后兼容，提供默认值）
    avg_connections: float = Field(default=0.0, description="平均每个疾病关联的基因数（trait_gene_associations）")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Combined Summary Response
# ============================================================================

class AnalysisSummaryResponse(BaseModel):
    """分析结果综合摘要"""

    high_affinity: HighAffinityAnalysis = Field(description="高亲和力分析统计")
    conservation: ConservationAnalysis = Field(description="保守性分析统计")
    epigenetic: EpigeneticAnalysis = Field(description="表观遗传分析统计")
    disease: DiseaseAnalysis = Field(description="疾病关联分析统计")

    model_config = ConfigDict(from_attributes=True)
