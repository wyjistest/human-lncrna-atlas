"""基因相关API路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, literal
from math import ceil

from app.core.utils import escape_like_pattern
from app.core.database import get_db
from app.core.cache import cache
from app.core.validators import MAX_ITEM_LENGTH, compute_pagination_offset, normalize_optional_str
from app.models import Gene, CoreGene, Species, Regulation, TraitGeneAssociation
from app.schemas.gene import (
    GeneDetail,
    GeneListItem,
    OrthologInfo,
    GeneOptionsResponse,
    GeneBatchResolveRequest,
    GeneBatchResolveResponse,
)
from app.schemas.common import PaginatedResponse

# Rate limiting - 复用 ChIP-seq 模块的限流实现
from app.routers.chipseq_rate_limit import rate_limit

router = APIRouter(prefix="/genes", tags=["genes"])

MAX_BATCH_IDENTIFIERS = 200
MAX_BATCH_TOTAL_CHARS = 5000
_SPECIES_SUFFIXES = ("_chimp", "_chimpanzee", "_macaque", "_marmoset")


@router.get("/options", response_model=GeneOptionsResponse)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
def get_gene_options(
    request: Request,  # Required for rate limiting
    species_id: Optional[int] = Query(None, ge=1, le=4, description="物种ID过滤"),
    gene_type: Optional[str] = Query(None, max_length=20, description="基因类型过滤（lncRNA/protein_coding）"),
    q: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="可选搜索关键词（gene_name / gene_ensembl_id 模糊匹配，建议用于 typeahead）",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=2000,
        description="可选返回上限（用于大列表下拉框分页/分批加载，最大 2000）",
    ),
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
    # 仅“全量 options”使用缓存：避免为每个 q/limit 组合生成大量缓存键
    normalized_q = normalize_optional_str(q)
    normalized_gene_type = normalize_optional_str(gene_type)
    if normalized_gene_type is not None and normalized_gene_type not in ("lncRNA", "protein_coding"):
        raise HTTPException(
            status_code=400,
            detail="gene_type must be 'lncRNA' or 'protein_coding'",
        )
    use_cache = (normalized_q is None and limit is None)
    if use_cache:
        cache_key = cache.make_options_key("genes", species_id=species_id, gene_type=normalized_gene_type)
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
    if normalized_gene_type:
        query = query.join(CoreGene, Gene.core_id == CoreGene.core_id)
        query = query.filter(CoreGene.gene_type == normalized_gene_type)

    # 应用物种过滤
    if species_id:
        query = query.filter(Gene.species_id == species_id)

    # 可选搜索（用于 typeahead）
    if normalized_q:
        escaped = escape_like_pattern(normalized_q)
        pattern = f"%{escaped}%"
        query = query.filter(
            or_(
                Gene.gene_name.ilike(pattern, escape="\\"),
                Gene.gene_ensembl_id.ilike(pattern, escape="\\"),
            )
        )

    # 可选 limit：如果提供搜索但未指定 limit，给一个保守默认值避免大返回
    effective_limit = limit
    if normalized_q and effective_limit is None:
        effective_limit = 200

    # SQLAlchemy 2.x: 必须先 order_by 再 limit/offset，否则会抛出运行时异常
    query = query.order_by(Gene.gene_name)

    if effective_limit is not None:
        query = query.limit(effective_limit)

    # 执行查询
    genes = query.all()

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
    if use_cache:
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
    lower = gene_name.lower()
    for suffix in _SPECIES_SUFFIXES:
        if lower.endswith(suffix):
            return gene_name[:-len(suffix)]

    return gene_name


def _strip_species_suffix(value: str) -> str:
    lower = value.lower()
    for suffix in _SPECIES_SUFFIXES:
        if lower.endswith(suffix):
            return value[:-len(suffix)]
    return value


def _expand_species_suffix_variants(value: str) -> List[str]:
    base = _strip_species_suffix(value)
    variants = {base}
    for suffix in _SPECIES_SUFFIXES:
        variants.add(base + suffix)
    return list(variants)


def _normalize_identifier_for_compare(value: str) -> str:
    if value.isdigit():
        try:
            return str(int(value))
        except Exception:
            return value
    return _strip_species_suffix(value).lower()


@router.get("", response_model=PaginatedResponse[GeneListItem])
@rate_limit("30/minute")  # Rate limit: 30 requests per minute per IP (aggregation query)
def list_genes(
    request: Request,  # Required for rate limiting
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    gene_type: Optional[str] = Query(None, max_length=20, description="基因类型（lncRNA/protein_coding）"),
    species_id: Optional[int] = Query(None, ge=1, le=4, description="物种ID"),
    chromosome: Optional[str] = Query(None, max_length=30, description="染色体"),
    search: Optional[str] = Query(None, max_length=100, description="搜索关键词（基因名/ID）"),
    has_regulation: Optional[bool] = Query(None, description="是否有调控关系"),
    min_regulation_count: Optional[int] = Query(None, ge=0, description="最小调控数量"),
    db: Session = Depends(get_db),
):
    """
    获取基因列表（支持分页和过滤）
    """
    normalized_search = normalize_optional_str(search)
    normalized_chromosome = normalize_optional_str(chromosome)
    normalized_gene_type = normalize_optional_str(gene_type)
    if normalized_gene_type is not None and normalized_gene_type not in ("lncRNA", "protein_coding"):
        raise HTTPException(
            status_code=400,
            detail="gene_type must be 'lncRNA' or 'protein_coding'",
        )

    # 构建基础查询
    query = (
        db.query(
            Gene.gene_id,
            Gene.core_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            # Use COALESCE to handle genes without core_id (returns 'unknown' if NULL)
            func.coalesce(CoreGene.gene_type, literal('unknown')).label("gene_type"),
            Species.display_name.label("species_name"),
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            func.count(Regulation.regulation_id).label("regulation_count"),
        )
        # Use outerjoin to include genes without core_id
        .outerjoin(CoreGene, Gene.core_id == CoreGene.core_id)
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
            CoreGene.gene_type,  # OK to group by even with outerjoin (NULL is a group)
            Species.display_name,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
        )
    )

    # 应用过滤条件
    if normalized_gene_type:
        query = query.filter(CoreGene.gene_type == normalized_gene_type)
    if species_id:
        query = query.filter(Gene.species_id == species_id)
    if normalized_chromosome:
        query = query.filter(Gene.chromosome == normalized_chromosome)
    if normalized_search:
        escaped = escape_like_pattern(normalized_search)
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

    # 总记录数（使用缓存）
    # 性能优化：避免对包含 GROUP BY/聚合字段的主查询直接做 count()。
    # - 无 has_regulation/min_regulation_count 时：直接统计 genes（不 JOIN regulations，不 GROUP BY）
    # - 有 HAVING 条件时：仅按 gene_id 分组，减少 GROUP BY 列数量
    count_cache_key = cache.make_list_key(
        "genes",
        gene_type=normalized_gene_type,
        species_id=species_id,
        chromosome=normalized_chromosome,
        search=normalized_search,
        has_regulation=has_regulation,
        min_regulation_count=min_regulation_count,
    )

    if has_regulation is None and min_regulation_count is None:
        count_query = (
            db.query(Gene.gene_id)
            .outerjoin(CoreGene, Gene.core_id == CoreGene.core_id)
        )

        if normalized_gene_type:
            count_query = count_query.filter(CoreGene.gene_type == normalized_gene_type)
        if species_id:
            count_query = count_query.filter(Gene.species_id == species_id)
        if normalized_chromosome:
            count_query = count_query.filter(Gene.chromosome == normalized_chromosome)
        if normalized_search:
            escaped = escape_like_pattern(normalized_search)
            search_pattern = f"%{escaped}%"
            count_query = count_query.filter(
                or_(
                    Gene.gene_name.ilike(search_pattern, escape='\\'),
                    Gene.gene_ensembl_id.ilike(search_pattern, escape='\\'),
                )
            )
    else:
        count_query = (
            db.query(Gene.gene_id)
            .outerjoin(CoreGene, Gene.core_id == CoreGene.core_id)
            .outerjoin(Regulation, Regulation.lncrna_gene_id == Gene.gene_id)
            .group_by(Gene.gene_id)
        )

        if normalized_gene_type:
            count_query = count_query.filter(CoreGene.gene_type == normalized_gene_type)
        if species_id:
            count_query = count_query.filter(Gene.species_id == species_id)
        if normalized_chromosome:
            count_query = count_query.filter(Gene.chromosome == normalized_chromosome)
        if normalized_search:
            escaped = escape_like_pattern(normalized_search)
            search_pattern = f"%{escaped}%"
            count_query = count_query.filter(
                or_(
                    Gene.gene_name.ilike(search_pattern, escape='\\'),
                    Gene.gene_ensembl_id.ilike(search_pattern, escape='\\'),
                )
            )

        if has_regulation is not None:
            if has_regulation:
                count_query = count_query.having(func.count(Regulation.regulation_id) > 0)
            else:
                count_query = count_query.having(func.count(Regulation.regulation_id) == 0)

        if min_regulation_count is not None:
            count_query = count_query.having(func.count(Regulation.regulation_id) >= min_regulation_count)

    total = cache.get_cached_count(count_query, count_cache_key)

    # 分页（添加 ORDER BY 确保分页稳定性）
    offset = compute_pagination_offset(page, page_size)
    items = query.order_by(Gene.gene_id).offset(offset).limit(page_size).all()

    # 转换为响应模型
    gene_list = []
    for item in items:
        # 如果gene_name以物种后缀结尾，则去除后缀
        # 注意：使用 endswith 而非 split，避免截断含下划线的基因名（如 TP53_AS1）
        gene_name = item.gene_name
        if gene_name:
            lower = gene_name.lower()
            for suffix in _SPECIES_SUFFIXES:
                if lower.endswith(suffix):
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


@router.post("/batch", response_model=GeneBatchResolveResponse)
@rate_limit("30/minute")  # Rate limit: 30 requests per minute per IP
def batch_resolve_genes(
    request: Request,  # Required for rate limiting
    payload: GeneBatchResolveRequest,
    db: Session = Depends(get_db),
):
    """
    批量解析基因标识符（gene_id / gene_name / gene_ensembl_id）。

    用途：
    - 前端 Genes 页的“批量查询”入口
    - 支持可选 species_id / gene_type 过滤，缩小匹配范围
    """
    normalized_gene_type = normalize_optional_str(payload.gene_type)
    if normalized_gene_type is not None and normalized_gene_type not in ("lncRNA", "protein_coding"):
        raise HTTPException(
            status_code=400,
            detail="gene_type must be 'lncRNA' or 'protein_coding'",
        )

    identifiers_raw: List[str] = []
    total_chars = 0
    for raw in payload.identifiers or []:
        normalized = normalize_optional_str(raw)
        if normalized is None:
            continue
        if len(normalized) > MAX_ITEM_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"identifier too long (max {MAX_ITEM_LENGTH} chars)",
            )
        total_chars += len(normalized)
        if total_chars > MAX_BATCH_TOTAL_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"identifiers total length too large (max {MAX_BATCH_TOTAL_CHARS} chars)",
            )
        identifiers_raw.append(normalized)

    if not identifiers_raw:
        raise HTTPException(status_code=400, detail="identifiers must not be empty")

    if len(identifiers_raw) > MAX_BATCH_IDENTIFIERS:
        raise HTTPException(
            status_code=400,
            detail=f"too many identifiers (max {MAX_BATCH_IDENTIFIERS})",
        )

    # 去重（保留输入顺序）
    seen = set()
    identifiers: List[str] = []
    for v in identifiers_raw:
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        identifiers.append(v)

    gene_ids: List[int] = []
    tokens: List[str] = []
    for v in identifiers:
        if v.isdigit():
            try:
                gene_ids.append(int(v))
            except Exception:
                tokens.append(v)
        else:
            tokens.append(v)

    expanded_tokens: set[str] = set()
    for token in tokens:
        for variant in _expand_species_suffix_variants(token):
            expanded_tokens.add(variant.lower())

    if not gene_ids and not expanded_tokens:
        raise HTTPException(status_code=400, detail="identifiers must not be empty")

    query = (
        db.query(
            Gene.gene_id,
            Gene.core_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            func.coalesce(CoreGene.gene_type, literal('unknown')).label("gene_type"),
            Species.display_name.label("species_name"),
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            func.count(Regulation.regulation_id).label("regulation_count"),
        )
        .outerjoin(CoreGene, Gene.core_id == CoreGene.core_id)
        .join(Species, Gene.species_id == Species.species_id)
        .outerjoin(Regulation, Regulation.lncrna_gene_id == Gene.gene_id)
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

    conditions = []
    if gene_ids:
        conditions.append(Gene.gene_id.in_(gene_ids))
    if expanded_tokens:
        conditions.append(func.lower(Gene.gene_name).in_(expanded_tokens))
        conditions.append(func.lower(Gene.gene_ensembl_id).in_(expanded_tokens))

    query = query.filter(or_(*conditions))

    if normalized_gene_type:
        query = query.filter(CoreGene.gene_type == normalized_gene_type)
    if payload.species_id:
        query = query.filter(Gene.species_id == payload.species_id)

    rows = query.order_by(Gene.gene_id).limit(2000).all()

    gene_list: List[GeneListItem] = []
    matched_norm: set[str] = set()
    for row in rows:
        gene_name = _remove_species_suffix(row.gene_name)
        gene_list.append(GeneListItem(
            gene_id=row.gene_id,
            core_id=row.core_id,
            gene_name=gene_name,
            gene_ensembl_id=row.gene_ensembl_id,
            gene_type=row.gene_type,
            species_name=row.species_name,
            chromosome=row.chromosome,
            gene_start=row.gene_start,
            gene_end=row.gene_end,
            regulation_count=row.regulation_count,
        ))

        matched_norm.add(str(row.gene_id))
        if row.gene_name:
            matched_norm.add(_normalize_identifier_for_compare(row.gene_name))
        if row.gene_ensembl_id:
            matched_norm.add(_normalize_identifier_for_compare(row.gene_ensembl_id))

    missing = [
        raw for raw in identifiers
        if _normalize_identifier_for_compare(raw) not in matched_norm
    ]

    return GeneBatchResolveResponse(items=gene_list, missing=missing)


@router.get("/{gene_id}", response_model=GeneDetail)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
def get_gene_detail(
    request: Request,  # Required for rate limiting
    gene_id: int,
    db: Session = Depends(get_db),
):
    """
    获取基因详细信息（包含统计和直系同源基因）

    Note: Handles genes without core_id (ortholog info unavailable)
    """
    # 查询基因基本信息 - use outerjoin to handle genes without core_id
    gene = (
        db.query(Gene, CoreGene, Species.display_name.label("species_name"))
        .outerjoin(CoreGene, Gene.core_id == CoreGene.core_id)
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
    # Only query if gene has core_id
    disease_count = 0
    if gene_obj.core_id is not None:
        disease_count = (
            db.query(func.count(TraitGeneAssociation.association_id))
            .filter(TraitGeneAssociation.core_id == gene_obj.core_id)
            .scalar()
        ) or 0

    # 查询直系同源基因 with regulation counts
    # Only query if gene has core_id (orthologs require core_id mapping)
    orthologs_result = []
    if gene_obj.core_id is not None:
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

        orthologs_result = [
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
        # Handle genes without core_id: return 'unknown' if no core_gene
        gene_type=core_gene.gene_type if core_gene else "unknown",
        chromosome=gene_obj.chromosome,
        gene_start=gene_obj.gene_start,
        gene_end=gene_obj.gene_end,
        strand=gene_obj.strand,
        regulation_count=regulation_count or 0,
        target_count=target_count or 0,
        disease_count=disease_count or 0,
        orthologs=orthologs_result,
        created_at=gene_obj.created_at,
    )


@router.get("/{gene_id}/orthologs", response_model=List[OrthologInfo])
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
def get_gene_orthologs(
    request: Request,  # Required for rate limiting
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
