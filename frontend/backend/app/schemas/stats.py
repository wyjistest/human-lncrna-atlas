"""统计信息数据模型"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class SpeciesStats(BaseModel):
    """物种统计"""

    species_id: int
    species_name: str
    gene_count: int = Field(description="基因数量")
    lncrna_count: int = Field(description="lncRNA数量")
    protein_coding_count: int = Field(description="protein_coding基因数量")
    regulation_count: int = Field(description="调控关系数量")

    model_config = ConfigDict(from_attributes=True)


class GeneTypeStats(BaseModel):
    """基因类型统计"""

    gene_type: str
    count: int


class OverviewStats(BaseModel):
    """全局概览统计"""

    total_core_genes: int = Field(description="总核心基因数")
    total_genes: int = Field(description="总基因数（含物种特异）")
    total_lncrna: int = Field(description="总lncRNA数")
    total_protein_coding: int = Field(description="总protein_coding基因数")
    total_regulations: int = Field(description="总调控关系数")
    total_traits: int = Field(description="总疾病/性状数")
    total_trait_associations: int = Field(description="总疾病关联数")

    # 物种统计
    species_stats: List[SpeciesStats] = Field(default_factory=list)

    # 数据库版本信息
    database_version: Optional[str] = None
    last_updated: Optional[str] = None


class GeneStats(BaseModel):
    """单个基因统计"""

    gene_id: int
    gene_name: Optional[str]
    regulation_count: int = Field(description="总调控关系数")
    target_count: int = Field(description="靶基因数量")
    disease_count: int = Field(description="关联疾病数量")
    species_count: int = Field(description="跨物种同源数量")

    model_config = ConfigDict(from_attributes=True)


class TopGene(BaseModel):
    """Top基因（按调控数量）"""

    gene_id: int
    core_id: int
    gene_name: Optional[str]
    gene_type: str
    regulation_count: int
    species_name: str


class TopDisease(BaseModel):
    """Top疾病（按关联基因数量）"""

    trait_id: int
    trait_name: str
    trait_category: Optional[str]
    gene_count: int
    lncrna_count: int


class ConservedRegulation(BaseModel):
    """保守调控关系"""

    lncrna_core_id: int
    lncrna_name: Optional[str]
    target_core_id: int
    target_name: Optional[str]
    species_count: int = Field(description="保守物种数量")
    species_list: List[str] = Field(description="保守物种列表")
    avg_binding_affinity: Optional[float] = None


class BARange(BaseModel):
    """结合亲和力范围"""

    min_ba: float = Field(description="最小结合亲和力")
    max_ba: float = Field(description="最大结合亲和力")
    avg_ba: float = Field(description="平均结合亲和力")
    total_count: int = Field(description="有效记录总数")


class BADistribution(BaseModel):
    """结合亲和力分布"""

    range_start: float
    range_end: float
    count: int


class DetailedStats(BaseModel):
    """详细统计信息"""

    species_distribution: List[Dict] = Field(description="物种分布")
    ba_distribution: List[BADistribution] = Field(description="BA分布直方图")
    top_lncrnas: List[Dict] = Field(description="Top lncRNA列表")
    ba_range: BARange = Field(description="BA范围")
