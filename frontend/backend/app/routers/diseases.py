"""疾病/性状相关API路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from math import ceil

from app.core.utils import escape_like_pattern
from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.models import (
    Trait,
    TraitGeneAssociation,
    CoreGene,
    Ontology,
    Gene,
    Species,
)
from app.schemas.disease import (
    TraitDetail,
    TraitGeneAssociationDetail,
)
from app.schemas.common import PaginatedResponse
from app.core.cache import cache

router = APIRouter(prefix="/diseases", tags=["diseases"])


@router.get("/options")
@rate_limit("60/minute")
def get_disease_options(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    获取疾病/性状选项列表（轻量级，用于下拉列表）

    返回所有疾病的 ID 和名称，支持 Redis 缓存（30 分钟 TTL）
    - 只查询 trait_id 和 trait_name 字段
    - 使用 DISTINCT 去重
    - 按 trait_name 排序
    """
    # 生成缓存键
    cache_key = cache._make_key("diseases:options")

    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # 查询数据库（只查询必要字段）
    traits = (
        db.query(Trait.trait_id, Trait.trait_name)
        .distinct()
        .order_by(Trait.trait_name)
        .all()
    )

    # 构造响应
    result = {
        "traits": [
            {"trait_id": trait.trait_id, "trait_name": trait.trait_name}
            for trait in traits
        ]
    }

    # 存入缓存（30 分钟 = 1800 秒）
    cache.set(cache_key, result, 1800)

    return result


@router.get("", response_model=PaginatedResponse[TraitGeneAssociationDetail])
@rate_limit("60/minute")
def list_diseases(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="搜索关键词（Trait/Ontology名称）"),
    db: Session = Depends(get_db),
):
    """
    获取疾病-Ontology关联列表（支持分页和过滤）
    """
    # 查询Trait-Ontology唯一组合
    query = (
        db.query(
            Trait.trait_id,
            Trait.trait_name,
            Trait.trait_category,
            Trait.trait_doid,
            Ontology.ontology_id,
            Ontology.ontology_name,
            Ontology.ontology_cl_id,
            TraitGeneAssociation.evidence_species_id,
            Species.display_name.label("species_name"),
            func.count(func.distinct(TraitGeneAssociation.core_id)).label("gene_count"),
            func.count(
                func.distinct(
                    case((CoreGene.gene_type == "lncRNA", TraitGeneAssociation.core_id), else_=None)
                )
            ).label("lncrna_count"),
        )
        .join(TraitGeneAssociation, Trait.trait_id == TraitGeneAssociation.trait_id)
        .join(Ontology, TraitGeneAssociation.ontology_id == Ontology.ontology_id)
        .join(CoreGene, TraitGeneAssociation.core_id == CoreGene.core_id)
        .outerjoin(Species, TraitGeneAssociation.evidence_species_id == Species.species_id)
        .group_by(
            Trait.trait_id,
            Trait.trait_name,
            Trait.trait_category,
            Trait.trait_doid,
            Ontology.ontology_id,
            Ontology.ontology_name,
            Ontology.ontology_cl_id,
            TraitGeneAssociation.evidence_species_id,
            Species.display_name,
        )
    )

    # 应用过滤（转义特殊字符防止意外匹配）
    if search:
        escaped = escape_like_pattern(search)
        search_pattern = f"%{escaped}%"
        query = query.filter(
            (Trait.trait_name.ilike(search_pattern, escape='\\')) |
            (Ontology.ontology_name.ilike(search_pattern, escape='\\'))
        )

    # 总数
    total = query.count()

    # 分页（添加 ORDER BY 确保分页稳定性）
    offset = (page - 1) * page_size
    items = query.order_by(Trait.trait_id, Ontology.ontology_id).offset(offset).limit(page_size).all()

    # 转换为响应模型
    result_list = [
        TraitGeneAssociationDetail(
            association_id=None,
            core_id=None,
            gene_name=None,
            gene_type=None,
            trait_id=item.trait_id,
            trait_name=item.trait_name,
            trait_category=item.trait_category,
            trait_doid=item.trait_doid,
            ontology_id=item.ontology_id,
            ontology_name=item.ontology_name,
            ontology_cl_id=item.ontology_cl_id,
            ontology_type=None,
            evidence_species_id=item.evidence_species_id,
            species_name=item.species_name,
            gene_count=item.gene_count or 0,
            lncrna_count=item.lncrna_count or 0,
            odds_ratio=None,
            fdr=None,
            trait_snp_pvalue=None,
            ontology_mw_pvalue=None,
            ontology_fold_enrichment=None,
            literature_support=None,
        )
        for item in items
    ]

    return PaginatedResponse(
        items=result_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{trait_id}", response_model=TraitDetail)
@rate_limit("120/minute")
def get_disease_detail(
    request: Request,
    trait_id: int,
    db: Session = Depends(get_db),
):
    """
    获取疾病/性状详细信息
    """
    # 查询疾病
    trait = db.query(Trait).filter(Trait.trait_id == trait_id).first()

    if not trait:
        raise HTTPException(status_code=404, detail="Disease/Trait not found")

    # 合并两个COUNT查询为单次查询（优化：减少数据库往返）
    # 使用 CASE WHEN 同时统计总基因数和 lncRNA 数
    stats = (
        db.query(
            func.count(func.distinct(TraitGeneAssociation.core_id)).label("gene_count"),
            func.count(func.distinct(
                case((CoreGene.gene_type == "lncRNA", TraitGeneAssociation.core_id), else_=None)
            )).label("lncrna_count"),
        )
        .join(CoreGene, TraitGeneAssociation.core_id == CoreGene.core_id)
        .filter(TraitGeneAssociation.trait_id == trait_id)
        .first()
    )

    gene_count = stats.gene_count or 0
    lncrna_count = stats.lncrna_count or 0

    return TraitDetail(
        trait_id=trait.trait_id,
        trait_name=trait.trait_name,
        trait_category=trait.trait_category,
        description=trait.description,
        trait_doid=trait.trait_doid,
        gene_count=gene_count or 0,
        lncrna_count=lncrna_count or 0,
    )


@router.get("/{trait_id}/genes", response_model=PaginatedResponse[TraitGeneAssociationDetail])
@rate_limit("60/minute")
def get_disease_genes(
    request: Request,
    trait_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    gene_type: Optional[str] = Query(None, description="基因类型过滤"),
    ontology_id: Optional[int] = Query(None, description="Ontology ID过滤"),
    db: Session = Depends(get_db),
):
    """
    获取疾病关联的基因列表
    """
    # 验证疾病存在
    trait = db.query(Trait).filter(Trait.trait_id == trait_id).first()
    if not trait:
        raise HTTPException(status_code=404, detail="Disease/Trait not found")

    # 构建基因名子查询（每个core_id取一个gene_name）
    # 使用 DISTINCT ON 替代相关子查询，避免 N+1 查询问题
    gene_name_subq = (
        db.query(
            Gene.core_id,
            Gene.gene_name,
        )
        .distinct(Gene.core_id)
        .order_by(Gene.core_id, Gene.gene_id)  # 确保每个core_id只取第一个
        .subquery("gene_names")
    )

    # 查询关联基因（使用 LEFT JOIN 替代相关子查询）
    query = (
        db.query(
            TraitGeneAssociation.association_id,
            TraitGeneAssociation.core_id,
            CoreGene.gene_type,
            TraitGeneAssociation.trait_id,
            Trait.trait_name,
            Trait.trait_category,
            TraitGeneAssociation.ontology_id,
            Ontology.ontology_type,
            Ontology.ontology_name,
            TraitGeneAssociation.odds_ratio,
            TraitGeneAssociation.fdr,
            TraitGeneAssociation.trait_snp_pvalue,
            TraitGeneAssociation.ontology_mw_pvalue,
            TraitGeneAssociation.ontology_fold_enrichment,
            TraitGeneAssociation.literature_support,
            TraitGeneAssociation.evidence_species_id,
            gene_name_subq.c.gene_name.label("gene_name"),
        )
        .join(CoreGene, TraitGeneAssociation.core_id == CoreGene.core_id)
        .join(Trait, TraitGeneAssociation.trait_id == Trait.trait_id)
        .join(Ontology, TraitGeneAssociation.ontology_id == Ontology.ontology_id)
        .outerjoin(gene_name_subq, TraitGeneAssociation.core_id == gene_name_subq.c.core_id)
        .filter(TraitGeneAssociation.trait_id == trait_id)
    )

    # 应用过滤
    if gene_type:
        query = query.filter(CoreGene.gene_type == gene_type)
    if ontology_id:
        query = query.filter(TraitGeneAssociation.ontology_id == ontology_id)

    # 总数
    total = query.count()

    # 分页（添加 ORDER BY 确保分页稳定性）
    offset = (page - 1) * page_size
    items = query.order_by(TraitGeneAssociation.association_id).offset(offset).limit(page_size).all()

    # 转换为响应模型
    association_list = [
        TraitGeneAssociationDetail(
            association_id=item.association_id,
            core_id=item.core_id,
            gene_name=item.gene_name,
            gene_type=item.gene_type,
            trait_id=item.trait_id,
            trait_name=item.trait_name,
            trait_category=item.trait_category,
            ontology_id=item.ontology_id,
            ontology_type=item.ontology_type,
            ontology_name=item.ontology_name,
            odds_ratio=item.odds_ratio,
            fdr=item.fdr,
            trait_snp_pvalue=item.trait_snp_pvalue,
            ontology_mw_pvalue=item.ontology_mw_pvalue,
            ontology_fold_enrichment=item.ontology_fold_enrichment,
            literature_support=item.literature_support,
            evidence_species_id=item.evidence_species_id,
        )
        for item in items
    ]

    return PaginatedResponse(
        items=association_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/gene/{gene_id}/associations", response_model=List[TraitGeneAssociationDetail])
@rate_limit("60/minute")
def get_gene_disease_associations(
    request: Request,
    gene_id: int,
    db: Session = Depends(get_db),
):
    """
    获取指定基因的所有疾病关联
    """
    # 查询基因的core_id
    gene = db.query(Gene.core_id, Gene.gene_name).filter(Gene.gene_id == gene_id).first()

    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # 查询疾病关联
    associations = (
        db.query(
            TraitGeneAssociation.association_id,
            TraitGeneAssociation.core_id,
            CoreGene.gene_type,
            TraitGeneAssociation.trait_id,
            Trait.trait_name,
            Trait.trait_category,
            TraitGeneAssociation.ontology_id,
            Ontology.ontology_type,
            Ontology.ontology_name,
            TraitGeneAssociation.odds_ratio,
            TraitGeneAssociation.fdr,
            TraitGeneAssociation.trait_snp_pvalue,
            TraitGeneAssociation.ontology_mw_pvalue,
            TraitGeneAssociation.ontology_fold_enrichment,
            TraitGeneAssociation.literature_support,
            TraitGeneAssociation.evidence_species_id,
        )
        .join(CoreGene, TraitGeneAssociation.core_id == CoreGene.core_id)
        .join(Trait, TraitGeneAssociation.trait_id == Trait.trait_id)
        .join(Ontology, TraitGeneAssociation.ontology_id == Ontology.ontology_id)
        .filter(TraitGeneAssociation.core_id == gene.core_id)
        .all()
    )

    return [
        TraitGeneAssociationDetail(
            association_id=item.association_id,
            core_id=item.core_id,
            gene_name=gene.gene_name,
            gene_type=item.gene_type,
            trait_id=item.trait_id,
            trait_name=item.trait_name,
            trait_category=item.trait_category,
            ontology_id=item.ontology_id,
            ontology_type=item.ontology_type,
            ontology_name=item.ontology_name,
            odds_ratio=item.odds_ratio,
            fdr=item.fdr,
            trait_snp_pvalue=item.trait_snp_pvalue,
            ontology_mw_pvalue=item.ontology_mw_pvalue,
            ontology_fold_enrichment=item.ontology_fold_enrichment,
            literature_support=item.literature_support,
            evidence_species_id=item.evidence_species_id,
        )
        for item in associations
    ]
