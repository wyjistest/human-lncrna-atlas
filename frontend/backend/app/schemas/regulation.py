"""调控关系数据模型"""
from typing import Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict, PlainSerializer
from decimal import Decimal

# 自定义 Decimal 序列化器：将 Decimal 转换为 float 以便 JSON 正确序列化为数字
DecimalAsFloat = Annotated[
    Decimal,
    PlainSerializer(lambda x: float(x) if x is not None else None, return_type=float)
]


class RegulationBase(BaseModel):
    """调控关系基础信息"""

    regulation_id: int
    lncrna_gene_id: int
    target_gene_id: int
    binding_affinity: Optional[DecimalAsFloat] = None
    best_avg_ba: Optional[DecimalAsFloat] = None

    model_config = ConfigDict(from_attributes=True)


class RegulationListItem(BaseModel):
    """调控关系列表项"""

    regulation_id: int
    species_id: int
    species_name: str
    lncrna_gene_id: int
    lncrna_gene_name: Optional[str] = None
    target_gene_id: int
    target_gene_name: Optional[str] = None
    target_chromosome: Optional[str] = None
    target_start: Optional[int] = None
    target_end: Optional[int] = None
    binding_affinity: Optional[DecimalAsFloat] = None
    best_avg_ba: Optional[DecimalAsFloat] = None
    num_peaks: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RegulationDetail(BaseModel):
    """调控关系详细信息"""

    regulation_id: int
    species_id: int
    species_name: str

    # lncRNA信息
    lncrna_gene_id: int
    lncrna_gene_name: Optional[str] = None
    lncrna_ensembl_id: Optional[str] = None

    # 靶基因信息
    target_gene_id: int
    target_gene_name: Optional[str] = None
    target_ensembl_id: Optional[str] = None
    target_chromosome: Optional[str] = None
    target_start: Optional[int] = None
    target_end: Optional[int] = None

    # 调控数据
    tfo_file: Optional[str] = None
    total_sites: Optional[int] = None
    kept_sites: Optional[int] = None
    num_peaks: Optional[int] = None
    best_peak_num: Optional[int] = None
    best_avg_ba: Optional[DecimalAsFloat] = None
    best_num_sites: Optional[int] = None

    # 最佳peak位置
    best_peak_chr: Optional[str] = None
    best_peak_start: Optional[int] = None
    best_peak_end: Optional[int] = None

    # 最佳结合位点
    best_site_ba: Optional[DecimalAsFloat] = None
    lncrna_start: Optional[int] = None
    lncrna_end: Optional[int] = None
    dna_start: Optional[int] = None
    dna_end: Optional[int] = None
    binding_affinity: Optional[DecimalAsFloat] = None

    # 序列数据
    lncrna_sequence: Optional[str] = None
    dna_sequence: Optional[str] = None

    # 序列可用性标记
    lncrna_sequence_available: bool = True
    dna_sequence_available: bool = True
    sequence_unavailable_reason: Optional[str] = None  # 如果不可用，说明原因

    model_config = ConfigDict(from_attributes=True)


class RegulationFilter(BaseModel):
    """调控关系过滤条件"""

    species_id: Optional[int] = Field(default=None, description="物种ID")
    lncrna_gene_id: Optional[int] = Field(default=None, description="lncRNA基因ID")
    target_gene_id: Optional[int] = Field(default=None, description="靶基因ID")
    min_ba: Optional[float] = Field(default=None, ge=0, description="最小结合亲和力")
    max_ba: Optional[float] = Field(default=None, ge=0, description="最大结合亲和力")
    chromosome: Optional[str] = Field(default=None, description="染色体")
    min_distance: Optional[int] = Field(default=None, description="最小距离（bp）")
    max_distance: Optional[int] = Field(default=None, description="最大距离（bp）")


class NetworkNode(BaseModel):
    """网络节点"""

    id: str = Field(description="节点ID")
    label: str = Field(description="节点标签")
    type: str = Field(description="节点类型（lncRNA/protein_coding）")
    gene_id: int
    core_id: int
    # Conservation data (Phase 2.2.1)
    conservation_label: Optional[str] = Field(
        default=None,
        description="4-bit binary conservation pattern: 1=human, 2=chimp, 3=macaque, 4=marmoset"
    )
    conservation_count: Optional[int] = Field(
        default=None,
        description="Number of species with this gene (1-4)"
    )


class NetworkEdge(BaseModel):
    """网络边"""

    source: str = Field(description="源节点ID")
    target: str = Field(description="目标节点ID")
    binding_affinity: Optional[float] = None
    regulation_id: int


class NetworkData(BaseModel):
    """网络数据"""

    nodes: list[NetworkNode]
    edges: list[NetworkEdge]
    stats: dict = Field(default_factory=dict, description="网络统计信息")


class LncRNAOption(BaseModel):
    """LncRNA 选项（轻量级，用于下拉框）"""

    gene_id: int
    gene_ensembl_id: str
    gene_name: Optional[str] = None
    species_id: int
    species_name: str
    regulation_count: int = Field(description="该 lncRNA 的调控关系数量")

    model_config = ConfigDict(from_attributes=True)


class LncRNAOptionsResponse(BaseModel):
    """LncRNA 选项响应"""

    lncrnas: list[LncRNAOption]


class TargetOption(BaseModel):
    """靶基因选项（轻量级，用于下拉框）"""

    gene_id: int
    gene_ensembl_id: str
    gene_name: Optional[str] = None
    species_id: int
    species_name: str
    lncrna_count: int = Field(description="调控该靶基因的 lncRNA 数量")

    model_config = ConfigDict(from_attributes=True)


class TargetOptionsResponse(BaseModel):
    """靶基因选项响应"""

    targets: list[TargetOption]
