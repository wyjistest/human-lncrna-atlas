"""基因相关API路由"""
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from math import ceil


def escape_like_pattern(value: str) -> str:
    """转义 LIKE 模式中的特殊字符 (%, _, \\)"""
    return re.sub(r'([%_\\])', r'\\\1', value)

from app.core.database import get_db
from app.core.cache import cache
from app.models import Gene, CoreGene, Species, Regulation, TraitGeneAssociation
from app.schemas.gene import (
    GeneDetail,
    GeneListItem,
    OrthologInfo,
    GeneFilter,
    GeneOption,
    GeneOptionsResponse,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/genes", tags=["genes"])


@router.get("/options", response_model=GeneOptionsResponse)
def get_gene_options(
    species_id: Optional[int] = Query(None, description="物种ID过滤"),
    gene_type: Optional[str] = Query(None, description="基因类型过滤（lncRNA/protein_coding）"),
    db: Session = Depends(get_db),
):
    """
    获取基因选项列表（轻量级，用于下拉框）

    性能优化：
    - 只返回必要字段（gene_id, gene_ensembl_id, gene_name, species_id, species_name）
    - Redis 缓存 30 分钟
    - 按 species_id 和 gene_type 分组缓存
    - 去除物种后缀（_chimp, _macaque, _marmoset）

    Args:
        species_id: 物种ID（可选）
        gene_type: 基因类型（可选）
        db: 数据库会话

    Returns:
        GeneOptionsResponse: 包含基因选项列表
    """
    # 构建缓存键
    cache_suffix = f"{species_id or 'all'}:{gene_type or 'all'}"
    cache_key = cache._make_key(f"genes:options:{cache_suffix}")

    # 尝试从缓存读取
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # 查询数据库（只查询必要字段）
    query = db.query(
        Gene.gene_id,
        Gene.gene_ensembl_id,
        Gene.gene_name,
        Gene.species_id,
        Species.display_name.label("species_name")
    ).join(Species, Gene.species_id == Species.species_id)

    # 如果需要按基因类型过滤，需要 JOIN core_genes
    if gene_type:
        query = query.join(CoreGene, Gene.core_id == CoreGene.core_id)
        query = query.filter(CoreGene.gene_type == gene_type)

    # 应用物种过滤
    if species_id:
        query = query.filter(Gene.species_id == species_id)

    # 执行查询并排序
    genes = query.order_by(Gene.gene_name).all()

    # 构建响应（去除物种后缀）
    result = {
        "genes": [
            {
                "gene_id": g.gene_id,
                "gene_ensembl_id": g.gene_ensembl_id,
                "gene_name": _remove_species_suffix(g.gene_name),
                "species_id": g.species_id,
                "species_name": g.species_name
            }
            for g in genes
        ]
    }

    # 写入缓存（30 分钟 = 1800 秒）
    cache.set(cache_key, result, 1800)

    return result


def _remove_species_suffix(gene_name: Optional[str]) -> Optional[str]:
    """
    去除基因名中的物种后缀

    Args:
        gene_name: 原始基因名

    Returns:
        去除后缀的基因名
    """
    if not gene_name:
        return gene_name

    # 检查并移除后缀
    suffixes = ['_chimp', '_macaque', '_marmoset']
    for suffix in suffixes:
        if gene_name.endswith(suffix):
            return gene_name[:-len(suffix)]

    return gene_name


@router.get("", response_model=PaginatedResponse[GeneListItem])
def list_genes(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    gene_type: Optional[str] = Query(None, description="基因类型（lncRNA/protein_coding）"),
    species_id: Optional[int] = Query(None, description="物种ID"),
    chromosome: Optional[str] = Query(None, description="染色体"),
    search: Optional[str] = Query(None, description="搜索关键词（基因名/ID）"),
    has_regulation: Optional[bool] = Query(None, description="是否有调控关系"),
    min_regulation_count: Optional[int] = Query(None, ge=0, description="最小调控数量"),
    db: Session = Depends(get_db),
):
    """
    获取基因列表（支持分页和过滤）
    """
    # 构建基础查询
    query = (
        db.query(
            Gene.gene_id,
            Gene.core_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            CoreGene.gene_type,
            Species.display_name.label("species_name"),
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            func.count(Regulation.regulation_id).label("regulation_count"),
        )
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .join(Species, Gene.species_id == Species.species_id)
        .outerjoin(
            Regulation,
            Regulation.lncrna_gene_id == Gene.gene_id,
        )
        .group_by(
            Gene.gene_id,
            Gene.core_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            CoreGene.gene_type,
            Species.display_name,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
        )
    )

    # 应用过滤条件
    if gene_type:
        query = query.filter(CoreGene.gene_type == gene_type)
    if species_id:
        query = query.filter(Gene.species_id == species_id)
    if chromosome:
        query = query.filter(Gene.chromosome == chromosome)
    if search:
        escaped = escape_like_pattern(search)
        search_pattern = f"%{escaped}%"
        query = query.filter(
            or_(
                Gene.gene_name.ilike(search_pattern, escape='\\'),
                Gene.gene_ensembl_id.ilike(search_pattern, escape='\\'),
            )
        )

    # 二次过滤（基于聚合结果）
    if has_regulation is not None:
        if has_regulation:
            query = query.having(func.count(Regulation.regulation_id) > 0)
        else:
            query = query.having(func.count(Regulation.regulation_id) == 0)

    if min_regulation_count is not None:
        query = query.having(func.count(Regulation.regulation_id) >= min_regulation_count)

    # 总记录数（应用所有过滤后，包括HAVING）
    total = query.count()

    # 分页（添加 ORDER BY 确保分页稳定性）
    offset = (page - 1) * page_size
    items = query.order_by(Gene.gene_id).offset(offset).limit(page_size).all()

    # 转换为响应模型
    gene_list = []
    for item in items:
        # 如果gene_name以物种后缀结尾，则去除后缀
        # 注意：使用 endswith 而非 split，避免截断含下划线的基因名（如 TP53_AS1）
        gene_name = item.gene_name
        if gene_name:
            for suffix in ['_chimp', '_macaque', '_marmoset']:
                if gene_name.endswith(suffix):
                    gene_name = gene_name[:-len(suffix)]
                    break

        gene_list.append(GeneListItem(
            gene_id=item.gene_id,
            core_id=item.core_id,
            gene_name=gene_name,
            gene_ensembl_id=item.gene_ensembl_id,
            gene_type=item.gene_type,
            species_name=item.species_name,
            chromosome=item.chromosome,
            gene_start=item.gene_start,
            gene_end=item.gene_end,
            regulation_count=item.regulation_count,
        ))

    return PaginatedResponse(
        items=gene_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{gene_id}", response_model=GeneDetail)
def get_gene_detail(
    gene_id: int,
    db: Session = Depends(get_db),
):
    """
    获取基因详细信息（包含统计和直系同源基因）
    """
    # 查询基因基本信息
    gene = (
        db.query(Gene, CoreGene, Species.display_name.label("species_name"))
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .join(Species, Gene.species_id == Species.species_id)
        .filter(Gene.gene_id == gene_id)
        .first()
    )

    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    gene_obj, core_gene, species_name = gene

    # 合并多个COUNT查询为单次查询（优化：减少数据库往返）
    stats = db.query(
        func.count(Regulation.regulation_id).label("regulation_count"),
        func.count(func.distinct(Regulation.target_gene_id)).label("target_count"),
    ).filter(Regulation.lncrna_gene_id == gene_id).first()

    regulation_count = stats.regulation_count or 0
    target_count = stats.target_count or 0

    # 疾病关联统计（需要单独查询，因为基于不同的表）
    disease_count = (
        db.query(func.count(TraitGeneAssociation.association_id))
        .filter(TraitGeneAssociation.core_id == gene_obj.core_id)
        .scalar()
    ) or 0

    # 查询直系同源基因 with regulation counts
    orthologs_query = (
        db.query(
            Gene.gene_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            Species.species_id,
            Species.display_name.label("species_name"),
            func.count(Regulation.regulation_id).label("regulation_count"),
        )
        .join(Species, Gene.species_id == Species.species_id)
        .outerjoin(Regulation, Regulation.lncrna_gene_id == Gene.gene_id)
        .filter(Gene.core_id == gene_obj.core_id)
        .filter(Gene.gene_id != gene_id)  # 排除自己
        .group_by(
            Gene.gene_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            Species.species_id,
            Species.display_name,
        )
    )

    orthologs = [
        OrthologInfo(
            species_id=o.species_id,
            species_name=o.species_name,
            gene_id=o.gene_id,
            gene_name=o.gene_name,
            gene_ensembl_id=o.gene_ensembl_id,
            chromosome=o.chromosome,
            gene_start=o.gene_start,
            gene_end=o.gene_end,
            regulation_count=o.regulation_count or 0,
        )
        for o in orthologs_query.all()
    ]

    return GeneDetail(
        gene_id=gene_obj.gene_id,
        core_id=gene_obj.core_id,
        species_id=gene_obj.species_id,
        species_name=species_name,
        gene_name=gene_obj.gene_name,
        gene_ensembl_id=gene_obj.gene_ensembl_id,
        gene_type=core_gene.gene_type,
        chromosome=gene_obj.chromosome,
        gene_start=gene_obj.gene_start,
        gene_end=gene_obj.gene_end,
        strand=gene_obj.strand,
        regulation_count=regulation_count or 0,
        target_count=target_count or 0,
        disease_count=disease_count or 0,
        orthologs=orthologs,
        created_at=gene_obj.created_at,
    )


@router.get("/{gene_id}/orthologs", response_model=List[OrthologInfo])
def get_gene_orthologs(
    gene_id: int,
    db: Session = Depends(get_db),
):
    """
    获取基因的直系同源基因列表

    Returns orthologs (genes with the same core_id) for the specified gene,
    including regulation counts for each ortholog.
    """
    # 查询基因的core_id
    gene = db.query(Gene.core_id).filter(Gene.gene_id == gene_id).first()

    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # 查询同源基因 with regulation counts
    # Uses left outer join to count regulations where the ortholog is the lncRNA
    orthologs = (
        db.query(
            Gene.gene_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            Species.species_id,
            Species.display_name.label("species_name"),
            func.count(Regulation.regulation_id).label("regulation_count"),
        )
        .join(Species, Gene.species_id == Species.species_id)
        .outerjoin(Regulation, Regulation.lncrna_gene_id == Gene.gene_id)
        .filter(Gene.core_id == gene.core_id)
        .filter(Gene.gene_id != gene_id)
        .group_by(
            Gene.gene_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            Species.species_id,
            Species.display_name,
        )
        .all()
    )

    return [
        OrthologInfo(
            species_id=o.species_id,
            species_name=o.species_name,
            gene_id=o.gene_id,
            gene_name=o.gene_name,
            gene_ensembl_id=o.gene_ensembl_id,
            chromosome=o.chromosome,
            gene_start=o.gene_start,
            gene_end=o.gene_end,
            regulation_count=o.regulation_count or 0,
        )
        for o in orthologs
    ]
