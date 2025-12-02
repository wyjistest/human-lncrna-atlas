"""疾病/性状相关数据模型"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class TraitBase(BaseModel):
    """性状/疾病基础信息"""

    trait_id: int
    trait_name: str
    trait_category: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TraitDetail(BaseModel):
    """性状/疾病详细信息"""

    trait_id: int
    trait_name: str
    trait_category: Optional[str] = None
    description: Optional[str] = None
    trait_doid: Optional[str] = None
    gene_count: int = Field(default=0, description="关联基因数量")
    lncrna_count: int = Field(default=0, description="关联lncRNA数量")

    model_config = ConfigDict(from_attributes=True)


class OntologyInfo(BaseModel):
    """本体/功能分类信息"""

    ontology_id: int
    ontology_name: str
    ontology_type: Optional[str] = None
    ontology_cl_id: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TraitGeneAssociationDetail(BaseModel):
    """性状-基因关联详细信息"""

    association_id: Optional[int] = None
    core_id: Optional[int] = None
    gene_name: Optional[str] = None
    gene_type: Optional[str] = None

    # 性状信息
    trait_id: int
    trait_name: str
    trait_category: Optional[str] = None
    trait_doid: Optional[str] = None

    # 本体信息
    ontology_id: int
    ontology_name: str
    ontology_cl_id: Optional[str] = None
    ontology_type: Optional[str] = None

    # 统计信息
    gene_count: Optional[int] = None
    lncrna_count: Optional[int] = None
    odds_ratio: Optional[Decimal] = None
    fdr: Optional[Decimal] = None
    trait_snp_pvalue: Optional[Decimal] = None
    ontology_mw_pvalue: Optional[Decimal] = None
    ontology_fold_enrichment: Optional[Decimal] = None
    literature_support: Optional[bool] = None

    # 证据物种
    evidence_species_id: Optional[int] = None
    species_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TraitFilter(BaseModel):
    """疾病/性状过滤条件"""

    trait_category: Optional[str] = Field(default=None, description="疾病分类")
    has_genes: Optional[bool] = Field(default=None, description="是否有关联基因")
    search: Optional[str] = Field(default=None, description="搜索关键词")
