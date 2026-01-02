"""统计信息API路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, desc, case

from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.core.cache import cache, CacheService
from app.core.validators import normalize_optional_str
from app.models import (
    Species,
    CoreGene,
    Gene,
    Regulation,
    Trait,
    TraitGeneAssociation,
)
from app.schemas.stats import (
    OverviewStats,
    SpeciesStats,
    TopGene,
    TopDisease,
    ConservedRegulation,
    BARange,
    BADistribution,
    DetailedStats,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewStats)
@rate_limit("30/minute")
def get_overview_stats(request: Request, db: Session = Depends(get_db)):
    """
    获取全局概览统计（缓存 1 小时）
    """
    # 尝试从缓存获取
    cache_key = cache.make_key("stats:overview")
    cached = cache.get(cache_key)
    if cached is not None:
        return OverviewStats(**cached)

    # 基础统计
    total_core_genes = db.query(func.count(CoreGene.core_id)).scalar()
    total_genes = db.query(func.count(Gene.gene_id)).scalar()
    total_regulations = db.query(func.count(Regulation.regulation_id)).scalar()
    total_traits = db.query(func.count(Trait.trait_id)).scalar()
    total_trait_associations = db.query(func.count(TraitGeneAssociation.association_id)).scalar()

    # lncRNA和protein_coding统计
    gene_type_stats = (
        db.query(CoreGene.gene_type, func.count(CoreGene.core_id))
        .group_by(CoreGene.gene_type)
        .all()
    )

    gene_type_dict = {gt: count for gt, count in gene_type_stats}
    total_lncrna = gene_type_dict.get("lncRNA", 0)
    total_protein_coding = gene_type_dict.get("protein_coding", 0)

    # 物种统计（使用子查询避免N+1问题）
    regulation_subq = (
        db.query(
            Regulation.species_id,
            func.count(Regulation.regulation_id).label("regulation_count")
        )
        .group_by(Regulation.species_id)
        .subquery("reg_counts")
    )

    species_stats_query = (
        db.query(
            Species.species_id,
            Species.display_name.label("species_name"),
            func.count(func.distinct(Gene.gene_id)).label("gene_count"),
            func.count(
                func.distinct(
                    case((CoreGene.gene_type == "lncRNA", Gene.gene_id), else_=None)
                )
            ).label("lncrna_count"),
            func.count(
                func.distinct(
                    case((CoreGene.gene_type == "protein_coding", Gene.gene_id), else_=None)
                )
            ).label("protein_coding_count"),
            func.coalesce(regulation_subq.c.regulation_count, 0).label("regulation_count"),
        )
        .outerjoin(Gene, Species.species_id == Gene.species_id)
        .outerjoin(CoreGene, Gene.core_id == CoreGene.core_id)
        .outerjoin(regulation_subq, Species.species_id == regulation_subq.c.species_id)
        .group_by(Species.species_id, Species.display_name, regulation_subq.c.regulation_count)
        .order_by(Species.species_id)  # 保证稳定排序：人类(1)→黑猩猩(2)→猕猴(3)→狨猴(4)
    )

    species_stats = [
        SpeciesStats(
            species_id=row.species_id,
            species_name=row.species_name,
            gene_count=row.gene_count or 0,
            lncrna_count=row.lncrna_count or 0,
            protein_coding_count=row.protein_coding_count or 0,
            regulation_count=row.regulation_count or 0,
        )
        for row in species_stats_query.all()
    ]

    result = OverviewStats(
        total_core_genes=total_core_genes or 0,
        total_genes=total_genes or 0,
        total_lncrna=total_lncrna,
        total_protein_coding=total_protein_coding,
        total_regulations=total_regulations or 0,
        total_traits=total_traits or 0,
        total_trait_associations=total_trait_associations or 0,
        species_stats=species_stats,
    )

    # 写入缓存（1小时）
    cache.set(cache_key, result, CacheService.TTL_STATS)

    return result


@router.get("/top-genes", response_model=List[TopGene])
@rate_limit("30/minute")
def get_top_genes(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="返回数量"),
    gene_type: Optional[str] = Query(None, max_length=32, description="基因类型过滤"),
    db: Session = Depends(get_db),
):
    """
    获取Top基因（按调控关系数量排序，缓存 1 小时）
    """
    normalized_gene_type = normalize_optional_str(gene_type)
    if normalized_gene_type is not None and normalized_gene_type not in ("lncRNA", "protein_coding"):
        raise HTTPException(
            status_code=400,
            detail="gene_type must be 'lncRNA' or 'protein_coding'",
        )

    # 构建缓存键（包含参数）
    # SECURITY/PERF: avoid embedding user-controlled strings in cache keys; use hashed key params.
    cache_key = cache.make_key("stats:top-genes", limit=limit, gene_type=normalized_gene_type)

    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached is not None:
        return [TopGene(**item) for item in cached]

    regulation_count = func.count(Regulation.regulation_id).label("regulation_count")
    query = (
        db.query(
            Gene.gene_id,
            Gene.core_id,
            Gene.gene_name,
            CoreGene.gene_type,
            Species.display_name.label("species_name"),
            regulation_count,
        )
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .join(Species, Gene.species_id == Species.species_id)
        .outerjoin(Regulation, Regulation.lncrna_gene_id == Gene.gene_id)
        .group_by(
            Gene.gene_id,
            Gene.core_id,
            Gene.gene_name,
            CoreGene.gene_type,
            Species.display_name,
        )
    )

    if normalized_gene_type:
        query = query.filter(CoreGene.gene_type == normalized_gene_type)

    query = query.order_by(regulation_count.desc()).limit(limit)

    results_raw = query.all()

    results = [
        TopGene(
            gene_id=row.gene_id,
            core_id=row.core_id,
            gene_name=row.gene_name,
            gene_type=row.gene_type,
            regulation_count=row.regulation_count or 0,
            species_name=row.species_name,
        )
        for row in results_raw
    ]

    # 写入缓存（1 小时）
    cache.set(cache_key, results, CacheService.TTL_STATS)

    return results


@router.get("/top-diseases", response_model=List[TopDisease])
@rate_limit("30/minute")
def get_top_diseases(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db),
):
    """
    获取Top疾病（按关联基因数量排序，缓存 1 小时）
    """
    # 缓存键
    cache_key = cache.make_key(f"stats:top-diseases:{limit}")

    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached is not None:
        return [TopDisease(**item) for item in cached]

    gene_count = func.count(func.distinct(TraitGeneAssociation.core_id)).label("gene_count")
    lncrna_count = func.count(
        func.distinct(
            case(
                (CoreGene.gene_type == "lncRNA", TraitGeneAssociation.core_id),
                else_=None,
            )
        )
    ).label("lncrna_count")

    query = (
        db.query(
            Trait.trait_id,
            Trait.trait_name,
            Trait.trait_category,
            gene_count,
            lncrna_count,
        )
        .join(TraitGeneAssociation, Trait.trait_id == TraitGeneAssociation.trait_id)
        .join(CoreGene, TraitGeneAssociation.core_id == CoreGene.core_id)
        .group_by(Trait.trait_id, Trait.trait_name, Trait.trait_category)
        .order_by(gene_count.desc())
        .limit(limit)
    )

    results_raw = query.all()

    results = [
        TopDisease(
            trait_id=row.trait_id,
            trait_name=row.trait_name,
            trait_category=row.trait_category,
            gene_count=row.gene_count or 0,
            lncrna_count=row.lncrna_count or 0,
        )
        for row in results_raw
    ]

    # 写入缓存（1 小时）
    cache.set(cache_key, results, CacheService.TTL_STATS)

    return results


@router.get("/conserved-regulations", response_model=List[ConservedRegulation])
@rate_limit("30/minute")
def get_conserved_regulations(
    request: Request,
    min_species: int = Query(2, ge=2, le=4, description="最少保守物种数"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    db: Session = Depends(get_db),
):
    """
    获取保守调控关系（在多个物种中保守的lncRNA-target对，缓存 1 小时）
    优化版：使用批量查询避免N+1问题
    """
    # 缓存键
    cache_key = cache.make_key(f"stats:conserved:{min_species}:{limit}")

    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached is not None:
        return [ConservedRegulation(**item) for item in cached]

    # 使用别名区分lncRNA和target基因
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")

    species_count = func.count(func.distinct(Regulation.species_id)).label("species_count")

    # 查询保守调控（包含基因名和物种信息）
    query = (
        db.query(
            LncRNAGene.core_id.label("lncrna_core_id"),
            TargetGene.core_id.label("target_core_id"),
            species_count,
            func.avg(Regulation.binding_affinity).label("avg_ba"),
            # 使用 GROUP_CONCAT / STRING_AGG 获取物种列表（PostgreSQL）
            func.string_agg(func.distinct(Species.display_name), ',').label("species_names"),
            # 获取第一个匹配的基因名
            func.min(LncRNAGene.gene_name).label("lncrna_name"),
            func.min(TargetGene.gene_name).label("target_name"),
        )
        .select_from(Regulation)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .join(Species, Regulation.species_id == Species.species_id)
        .group_by(LncRNAGene.core_id, TargetGene.core_id)
        .having(species_count >= min_species)
        .order_by(species_count.desc())
        .limit(limit)
    )

    results_raw = query.all()

    # 构建结果列表（无需额外查询）
    results = [
        ConservedRegulation(
            lncrna_core_id=row.lncrna_core_id,
            lncrna_name=row.lncrna_name,
            target_core_id=row.target_core_id,
            target_name=row.target_name,
            species_count=row.species_count,
            species_list=row.species_names.split(',') if row.species_names else [],
            avg_binding_affinity=float(row.avg_ba) if row.avg_ba else None,
        )
        for row in results_raw
    ]

    # 写入缓存（1 小时）
    cache.set(cache_key, results, CacheService.TTL_STATS)

    return results


@router.get("/ba-range", response_model=BARange)
@rate_limit("30/minute")
def get_ba_range(request: Request, db: Session = Depends(get_db)):
    """
    获取结合亲和力范围（缓存 1 小时）
    用于前端动态设置筛选器范围
    """
    # 尝试从缓存获取
    cache_key = cache.make_key("stats:ba-range")
    cached = cache.get(cache_key)
    if cached is not None:
        return BARange(**cached)

    result = db.query(
        func.min(Regulation.binding_affinity).label("min_ba"),
        func.max(Regulation.binding_affinity).label("max_ba"),
        func.avg(Regulation.binding_affinity).label("avg_ba"),
        func.count(Regulation.regulation_id).label("total_count"),
    ).filter(Regulation.binding_affinity.isnot(None)).first()

    ba_range = BARange(
        min_ba=float(result.min_ba) if result.min_ba else 0,
        max_ba=float(result.max_ba) if result.max_ba else 100,
        avg_ba=round(float(result.avg_ba), 2) if result.avg_ba else 0,
        total_count=result.total_count or 0,
    )

    # 写入缓存
    cache.set(cache_key, ba_range, CacheService.TTL_STATS)

    return ba_range


@router.get("/detailed", response_model=DetailedStats)
@rate_limit("30/minute")
def get_detailed_stats(
    request: Request,
    buckets: int = Query(10, ge=5, le=50, description="BA分布直方图桶数"),
    top_limit: int = Query(10, ge=1, le=100, description="Top lncRNA数量"),
    db: Session = Depends(get_db),
):
    """
    获取详细统计信息（包含多维度数据，缓存 1 小时）
    包含物种分布、BA分布直方图、Top lncRNA
    """
    # 缓存键
    cache_key = cache.make_key(f"stats:detailed:{buckets}:{top_limit}")

    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached is not None:
        return DetailedStats(**cached)

    # 1. BA范围
    ba_result = db.query(
        func.min(Regulation.binding_affinity).label("min_ba"),
        func.max(Regulation.binding_affinity).label("max_ba"),
        func.avg(Regulation.binding_affinity).label("avg_ba"),
        func.count(Regulation.regulation_id).label("total_count"),
    ).filter(Regulation.binding_affinity.isnot(None)).first()

    ba_range = BARange(
        min_ba=float(ba_result.min_ba) if ba_result.min_ba else 0,
        max_ba=float(ba_result.max_ba) if ba_result.max_ba else 100,
        avg_ba=round(float(ba_result.avg_ba), 2) if ba_result.avg_ba else 0,
        total_count=ba_result.total_count or 0,
    )

    # 2. 物种分布
    species_dist = (
        db.query(
            Species.species_id,
            Species.display_name.label("species_name"),
            func.count(Regulation.regulation_id).label("count"),
        )
        .join(Regulation, Species.species_id == Regulation.species_id)
        .group_by(Species.species_id, Species.display_name)
        .all()
    )

    species_distribution = [
        {"species_id": row.species_id, "species_name": row.species_name, "count": row.count}
        for row in species_dist
    ]

    # 3. BA分布直方图（优化：单次查询替代N次循环查询）
    min_ba = float(ba_result.min_ba) if ba_result.min_ba else 0
    max_ba = float(ba_result.max_ba) if ba_result.max_ba else 100
    # 防止除零错误
    if max_ba == min_ba:
        bucket_size = 1.0
    else:
        bucket_size = (max_ba - min_ba) / buckets

    # 使用 FLOOR 计算桶索引，然后 GROUP BY 一次性获取所有桶的计数
    # 这比 N 次独立查询高效得多（80万条数据从 N 次查询变为 1 次）
    bucket_expr = func.floor((Regulation.binding_affinity - min_ba) / bucket_size)

    bucket_counts_query = (
        db.query(
            bucket_expr.label("bucket_index"),
            func.count(Regulation.regulation_id).label("count"),
        )
        .filter(Regulation.binding_affinity.isnot(None))
        .group_by(bucket_expr)
        .all()
    )

    # 将查询结果转换为字典便于快速查找
    bucket_counts = {int(row.bucket_index): row.count for row in bucket_counts_query}

    # 构建完整的分布列表（包括计数为0的桶）
    ba_distribution = []
    for i in range(buckets):
        range_start = min_ba + i * bucket_size
        range_end = min_ba + (i + 1) * bucket_size

        # 最后一个桶包含边界值，可能被计算为 bucket_index = buckets
        if i == buckets - 1:
            count = bucket_counts.get(i, 0) + bucket_counts.get(buckets, 0)
        else:
            count = bucket_counts.get(i, 0)

        ba_distribution.append(
            BADistribution(
                range_start=round(range_start, 2),
                range_end=round(range_end, 2),
                count=count,
            )
        )

    # 4. Top lncRNA（按调控关系数量）
    top_lncrnas_query = (
        db.query(
            Gene.gene_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Species.display_name.label("species_name"),
            func.count(Regulation.regulation_id).label("regulation_count"),
        )
        .join(Regulation, Regulation.lncrna_gene_id == Gene.gene_id)
        .join(Species, Gene.species_id == Species.species_id)
        .group_by(Gene.gene_id, Gene.gene_name, Gene.gene_ensembl_id, Species.display_name)
        .order_by(desc(func.count(Regulation.regulation_id)))
        .limit(top_limit)
    )

    top_lncrnas = [
        {
            "gene_id": row.gene_id,
            "gene_name": row.gene_name,
            "gene_ensembl_id": row.gene_ensembl_id,
            "species_name": row.species_name,
            "regulation_count": row.regulation_count,
        }
        for row in top_lncrnas_query.all()
    ]

    result = DetailedStats(
        species_distribution=species_distribution,
        ba_distribution=ba_distribution,
        top_lncrnas=top_lncrnas,
        ba_range=ba_range,
    )

    # 写入缓存（1 小时）
    cache.set(cache_key, result, CacheService.TTL_STATS)

    return result


@router.get("/cache-status")
@rate_limit("30/minute")
def get_cache_status(request: Request):
    """
    获取缓存状态信息
    """
    return cache.get_stats()
