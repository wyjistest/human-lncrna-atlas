"""网络分析相关数据模型（用于 OpenAPI 类型与响应约束）"""

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AvailableCombination(BaseModel):
    """Disease network 可用组合（trait + ontology + species）"""

    trait_id: int
    ontology_id: int
    ontology_name: str
    species_id: int = Field(description="证据物种 ID")


class AvailableCombinationsResponse(BaseModel):
    """可用组合列表响应"""

    combinations: list[AvailableCombination]


class NetworkGeneConnections(BaseModel):
    """网络节点点击详情中的连接统计"""

    as_source: int
    as_target: int
    total: int
    total_ba: float = Field(description="Total binding affinity sum")


class NetworkGeneDetail(BaseModel):
    """网络节点点击详情（/network/gene/{gene_id}/detail）"""

    gene_id: int
    gene_name: str
    gene_ensembl_id: Optional[str] = None
    gene_type: str
    species_id: int
    species_name: Optional[str] = None
    chromosome: Optional[str] = None
    gene_start: Optional[int] = None
    gene_end: Optional[int] = None
    # Backward compatibility: old field names used by some clients (deprecated)
    start: Optional[int] = Field(
        default=None,
        description="Deprecated: use gene_start",
        json_schema_extra={"deprecated": True},
    )
    end: Optional[int] = Field(
        default=None,
        description="Deprecated: use gene_end",
        json_schema_extra={"deprecated": True},
    )
    strand: Optional[str] = None
    core_id: Optional[int] = None
    conservation_label: str
    conservation_count: int
    connections: NetworkGeneConnections

    model_config = ConfigDict(from_attributes=True)


class SpeciesTargetGene(BaseModel):
    """跨物种对比：单个物种的靶基因条目"""

    target_gene_id: int
    target_name: Optional[str] = None
    target_core_id: int
    binding_affinity: Optional[float] = None


class SpeciesNetworkData(BaseModel):
    """跨物种对比：单个物种网络数据"""

    lncrna_gene_id: int
    species_id: int
    species_name: str
    target_count: int
    total_target_count: int
    truncated: bool
    targets: list[SpeciesTargetGene]


class SpeciesNetworkComparisonResponse(BaseModel):
    """跨物种网络对比响应（/network/compare）"""

    lncrna_core_id: int
    # 注意：JSON 对象 key 必须是字符串，因此这里显式使用 str 作为 key
    species_names: dict[str, str]
    # 语义上 key 为 species_id（1-4）；序列化时会转为字符串
    species_networks: dict[int, SpeciesNetworkData]
    conserved_target_count: int
    conserved_targets: list[int]
