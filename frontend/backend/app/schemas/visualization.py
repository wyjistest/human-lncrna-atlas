"""
可视化数据 Schema 定义

用于高级可视化（Sankey Flow Diagram）的数据模型
"""
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Sankey Flow Diagram Schemas
# ============================================================================

class SankeyNode(BaseModel):
    """Sankey 图节点"""

    id: str = Field(description="节点唯一标识 (lncrna_123, gene_456, disease_789)")
    name: str = Field(description="节点显示名称")
    layer: int = Field(description="节点层级 (0=lncRNA, 1=gene, 2=disease)")

    model_config = ConfigDict(from_attributes=True)


class SankeyLink(BaseModel):
    """Sankey 图连接"""

    source: str = Field(description="源节点 ID")
    target: str = Field(description="目标节点 ID")
    value: float = Field(description="连接权重（平均结合亲和力）")
    flow_count: int = Field(description="流经的记录数（调控关系数/疾病关联数）")

    model_config = ConfigDict(from_attributes=True)


class SankeyData(BaseModel):
    """Sankey 图数据容器"""

    nodes: List[SankeyNode] = Field(description="节点列表")
    links: List[SankeyLink] = Field(description="连接列表")

    model_config = ConfigDict(from_attributes=True)


class SankeyStats(BaseModel):
    """Sankey 图统计信息"""

    total_lncrnas: int = Field(description="lncRNA 节点数")
    total_genes: int = Field(description="基因节点数")
    total_diseases: int = Field(description="疾病节点数")
    total_regulations: int = Field(description="调控关系数（lncRNA->gene）")
    total_associations: int = Field(description="疾病关联数（gene->disease）")
    avg_binding_affinity: float = Field(description="平均结合亲和力")
    species_id: int = Field(description="物种 ID")

    model_config = ConfigDict(from_attributes=True)


class SankeyResponse(BaseModel):
    """Sankey 图响应模型"""

    success: bool = Field(default=True, description="请求是否成功")
    data: SankeyData = Field(description="Sankey 图数据")
    stats: SankeyStats = Field(description="统计信息")
    query_params: Dict[str, Any] = Field(description="查询参数记录")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Chord Diagram Schemas
# ============================================================================

class ChordNode(BaseModel):
    """Chord 图节点"""

    id: str = Field(description="节点唯一标识 (lncrna_123, gene_456)")
    name: str = Field(description="节点显示名称")
    category: str = Field(description="节点类型：lncrna | gene")
    value: float = Field(description="节点权重（用于节点大小）")

    model_config = ConfigDict(from_attributes=True)


class ChordLink(BaseModel):
    """Chord 图连接"""

    source: str = Field(description="源节点 ID")
    target: str = Field(description="目标节点 ID")
    value: float = Field(description="连接权重（结合亲和力）")

    model_config = ConfigDict(from_attributes=True)


class ChordData(BaseModel):
    """Chord 图数据容器"""

    nodes: List[ChordNode] = Field(description="节点列表")
    links: List[ChordLink] = Field(description="连接列表")
    matrix: List[List[float]] = Field(description="邻接矩阵（用于 D3 chord 图）")

    model_config = ConfigDict(from_attributes=True)


class ChordStats(BaseModel):
    """Chord 图统计信息"""

    total_nodes: int = Field(description="总节点数")
    total_lncrnas: int = Field(description="lncRNA 节点数")
    total_genes: int = Field(description="基因节点数")
    total_links: int = Field(description="连接数（调控关系数）")
    avg_binding_affinity: float = Field(description="平均结合亲和力")
    max_binding_affinity: float = Field(description="最大结合亲和力")
    min_binding_affinity: float = Field(description="最小结合亲和力")
    species_id: int = Field(description="物种 ID")

    model_config = ConfigDict(from_attributes=True)


class ChordResponse(BaseModel):
    """Chord 图响应模型"""

    success: bool = Field(default=True, description="请求是否成功")
    data: ChordData = Field(description="Chord 图数据")
    stats: ChordStats = Field(description="统计信息")
    query_params: Dict[str, Any] = Field(description="查询参数记录")

    model_config = ConfigDict(from_attributes=True)
