"""基因相关数据模型"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class GeneBase(BaseModel):
    """基因基础信息"""

    gene_id: int
    gene_name: Optional[str] = None
    gene_ensembl_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GeneListItem(BaseModel):
    """基因列表项（用于列表展示）"""

    gene_id: int
    core_id: int
    gene_name: Optional[str] = None
    gene_ensembl_id: Optional[str] = None
    gene_type: str = Field(description="基因类型（lncRNA/protein_coding）")
    species_name: str
    chromosome: Optional[str] = None
    gene_start: Optional[int] = None
    gene_end: Optional[int] = None
    regulation_count: Optional[int] = Field(default=0, description="调控关系数量")

    model_config = ConfigDict(from_attributes=True)


class CoreGeneInfo(BaseModel):
    """核心基因信息（跨物种）"""

    core_id: int
    gene_type: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrthologInfo(BaseModel):
    """直系同源基因信息"""

    species_name: str
    species_id: int
    gene_id: int
    gene_name: Optional[str] = None
    gene_ensembl_id: Optional[str] = None
    chromosome: Optional[str] = None
    gene_start: Optional[int] = None
    gene_end: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class GeneDetail(BaseModel):
    """基因详细信息"""

    # 基本信息
    gene_id: int
    core_id: int
    species_id: int
    species_name: str
    gene_name: Optional[str] = None
    gene_ensembl_id: Optional[str] = None
    gene_type: str = Field(description="基因类型（来自core_genes）")

    # 位置信息
    chromosome: Optional[str] = None
    gene_start: Optional[int] = None
    gene_end: Optional[int] = None
    strand: Optional[str] = None

    # 统计信息
    regulation_count: int = Field(default=0, description="调控关系数量")
    target_count: int = Field(default=0, description="靶基因数量")
    disease_count: int = Field(default=0, description="关联疾病数量")

    # 直系同源基因
    orthologs: List[OrthologInfo] = Field(default_factory=list)

    # 时间戳
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GeneFilter(BaseModel):
    """基因过滤条件"""

    gene_type: Optional[str] = Field(default=None, description="基因类型（lncRNA/protein_coding）")
    species_id: Optional[int] = Field(default=None, description="物种ID")
    chromosome: Optional[str] = Field(default=None, description="染色体")
    has_regulation: Optional[bool] = Field(default=None, description="是否有调控关系")
    has_disease: Optional[bool] = Field(default=None, description="是否有疾病关联")
    min_regulation_count: Optional[int] = Field(default=None, description="最小调控数量")
    search: Optional[str] = Field(default=None, description="搜索关键词（基因名/ID）")
