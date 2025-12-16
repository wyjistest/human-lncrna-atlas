"""数据导出 API Schema 定义"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# High-Affinity Export Schemas
# ============================================================================

class HighAffinityRegulationExport(BaseModel):
    """高亲和力调控关系导出数据模型"""

    lncrna_gene_id: int = Field(description="lncRNA 基因 ID")
    lncrna_name: str = Field(description="lncRNA 基因名")
    target_gene_id: int = Field(description="靶基因 ID")
    target_name: str = Field(description="靶基因名")
    binding_affinity: float = Field(description="结合亲和力 (BA)")
    species_id: int = Field(description="物种 ID")
    species_name: str = Field(description="物种名称")
    chr: str = Field(description="染色体")
    start_in_genome: int = Field(description="基因组起始位置")
    end_in_genome: int = Field(description="基因组终止位置")

    model_config = ConfigDict(from_attributes=True)


class HighAffinityExportResponse(BaseModel):
    """高亲和力导出响应"""

    data: List[HighAffinityRegulationExport] = Field(description="调控关系数据列表")
    total: int = Field(description="总记录数")
    query_params: dict = Field(description="查询参数")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Conservation Export Schemas
# ============================================================================

class ConservationExport(BaseModel):
    """保守性数据导出模型"""

    core_id: int = Field(description="核心 ID")
    lncrna_names: List[str] = Field(description="lncRNA 名称列表")
    species_count: int = Field(description="保守物种数")
    total_regulations: int = Field(description="总调控关系数")
    avg_binding_affinity: float = Field(description="平均结合亲和力")
    conserved_targets: List[str] = Field(description="保守靶基因列表")

    model_config = ConfigDict(from_attributes=True)


class ConservationExportResponse(BaseModel):
    """保守性导出响应"""

    data: List[ConservationExport] = Field(description="保守性数据列表")
    total: int = Field(description="总记录数")
    query_params: dict = Field(description="查询参数")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ChIP-seq Overlap Export Schemas
# ============================================================================

class ChipseqOverlapExport(BaseModel):
    """ChIP-seq 重叠导出模型"""

    regulation_id: int = Field(description="调控关系 ID")
    lncrna_name: str = Field(description="lncRNA 名称")
    target_name: str = Field(description="靶基因名称")
    binding_affinity: float = Field(description="结合亲和力")
    mark_name: str = Field(description="组蛋白标记名称")
    peak_score: float = Field(description="ChIP-seq 峰得分")
    peak_chr: str = Field(description="峰染色体")
    peak_start: int = Field(description="峰起始位置")
    peak_end: int = Field(description="峰终止位置")
    cell_type: str = Field(description="细胞类型")

    model_config = ConfigDict(from_attributes=True)


class ChipseqOverlapExportResponse(BaseModel):
    """ChIP-seq 重叠导出响应"""

    data: List[ChipseqOverlapExport] = Field(description="ChIP-seq 重叠数据列表")
    total: int = Field(description="总记录数")
    query_params: dict = Field(description="查询参数")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Disease Network Export Schemas
# ============================================================================

class NetworkNode(BaseModel):
    """网络节点"""

    id: str = Field(description="节点 ID")
    type: str = Field(description="节点类型 (disease/gene/lncrna)")
    name: str = Field(description="节点名称")

    model_config = ConfigDict(from_attributes=True)


class NetworkEdge(BaseModel):
    """网络边"""

    source: str = Field(description="源节点 ID")
    target: str = Field(description="目标节点 ID")
    type: str = Field(description="边类型 (disease-gene/regulation)")
    weight: Optional[float] = Field(None, description="边权重 (BA/p-value)")

    model_config = ConfigDict(from_attributes=True)


class DiseaseNetworkExportResponse(BaseModel):
    """疾病网络导出响应"""

    nodes: List[NetworkNode] = Field(description="网络节点列表")
    edges: List[NetworkEdge] = Field(description="网络边列表")
    query_params: dict = Field(description="查询参数")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Regulations Export Schemas (Phase 9.3: 前端 xlsx 迁移到后端)
# ============================================================================

class RegulationExport(BaseModel):
    """调控关系导出数据模型"""

    regulation_id: int = Field(description="调控关系 ID")
    lncrna_gene_name: Optional[str] = Field(None, description="lncRNA 基因名")
    target_gene_name: Optional[str] = Field(None, description="靶基因名")
    species_name: str = Field(description="物种名称")
    target_chromosome: Optional[str] = Field(None, description="染色体")
    target_start: Optional[int] = Field(None, description="起始位置")
    target_end: Optional[int] = Field(None, description="终止位置")
    binding_affinity: Optional[float] = Field(None, description="结合亲和力 (BA)")
    num_peaks: Optional[int] = Field(None, description="峰数量")

    model_config = ConfigDict(from_attributes=True)


class RegulationsExportResponse(BaseModel):
    """调控关系导出响应 (JSON 格式)"""

    data: List[RegulationExport] = Field(description="调控关系数据列表")
    total: int = Field(description="总记录数")
    query_params: dict = Field(description="查询参数")

    model_config = ConfigDict(from_attributes=True)
