"""调控关系API路由"""
import logging
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, aliased
from sqlalchemy import desc, func
from math import ceil

from app.core.utils import escape_like_pattern
from app.core.database import get_db
from app.core.cache import cache
from app.core.validators import (
    compute_pagination_offset,
    normalize_optional_str,
    parse_comma_list,
    parse_int_list,
)
from app.routers.chipseq_rate_limit import rate_limit
from app.models import Regulation, Gene, Species, Sequence
from app.schemas.regulation import (
    RegulationDetail,
    RegulationListItem,
    LncRNAOptionsResponse,
    TargetOptionsResponse,
)
from app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regulations", tags=["regulations"])

# 染色体格式校验（chr1-chr22, chrX, chrY, chrM）
_CHR_PATTERN = re.compile(r"^chr([1-9]|1[0-9]|2[0-2]|X|Y|M)$", re.IGNORECASE)


@router.get("/lncrna-options", response_model=LncRNAOptionsResponse)
@rate_limit("60/minute")
def get_lncrna_options(
    request: Request,
    species_id: Optional[int] = Query(None, ge=1, le=4, description="物种ID过滤"),
    db: Session = Depends(get_db),
):
    """
    获取 lncRNA 选项列表（轻量级，用于下拉框）

    性能优化：
    - 只返回有调控关系的 lncRNA
    - 包含每个 lncRNA 的调控数量
    - Redis 缓存 30 分钟
    - 按 species_id 分组缓存

    Args:
        species_id: 物种ID（可选）
        db: 数据库会话

    Returns:
        LncRNAOptionsResponse: 包含 lncRNA 选项列表
    """
    # 构建缓存键
    cache_key = cache.make_options_key("regulations:lncrna", species_id=species_id)

    # 尝试从缓存读取
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("[CACHE HIT] regulations:lncrna-options")
        return cached

    logger.debug("[CACHE MISS] regulations:lncrna-options")

    # 查询数据库：从 regulations 表聚合获取有调控关系的 lncRNA
    query = db.query(
        Gene.gene_id,
        Gene.gene_ensembl_id,
        Gene.gene_name,
        Gene.species_id,
        Species.display_name.label("species_name"),
        func.count(Regulation.regulation_id).label("regulation_count")
    ).join(
        Regulation, Gene.gene_id == Regulation.lncrna_gene_id
    ).join(
        Species, Gene.species_id == Species.species_id
    ).group_by(
        Gene.gene_id,
        Gene.gene_ensembl_id,
        Gene.gene_name,
        Gene.species_id,
        Species.display_name
    )

    # 应用物种过滤
    if species_id:
        query = query.filter(Gene.species_id == species_id)

    # 执行查询并排序
    lncrnas = query.order_by(Gene.gene_name).all()

    # 构建响应
    result = {
        "lncrnas": [
            {
                "gene_id": lnc.gene_id,
                "gene_ensembl_id": lnc.gene_ensembl_id,
                "gene_name": lnc.gene_name,
                "species_id": lnc.species_id,
                "species_name": lnc.species_name,
                "regulation_count": lnc.regulation_count
            }
            for lnc in lncrnas
        ]
    }

    # 写入缓存（30 分钟 = 1800 秒）
    cache.set(cache_key, result, 1800)

    return result


@router.get("/target-options", response_model=TargetOptionsResponse)
@rate_limit("60/minute")
def get_target_options(
    request: Request,
    species_id: Optional[int] = Query(None, ge=1, le=4, description="物种ID过滤"),
    db: Session = Depends(get_db),
):
    """
    获取靶基因选项列表（轻量级，用于下拉框）

    性能优化：
    - 只返回被调控的基因
    - 包含每个靶基因被多少个 lncRNA 调控
    - Redis 缓存 30 分钟
    - 按 species_id 分组缓存

    Args:
        species_id: 物种ID（可选）
        db: 数据库会话

    Returns:
        TargetOptionsResponse: 包含靶基因选项列表
    """
    # 构建缓存键
    cache_key = cache.make_options_key("regulations:target", species_id=species_id)

    # 尝试从缓存读取
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("[CACHE HIT] regulations:target-options")
        return cached

    logger.debug("[CACHE MISS] regulations:target-options")

    # 查询数据库：从 regulations 表聚合获取被调控的基因
    query = db.query(
        Gene.gene_id,
        Gene.gene_ensembl_id,
        Gene.gene_name,
        Gene.species_id,
        Species.display_name.label("species_name"),
        func.count(func.distinct(Regulation.lncrna_gene_id)).label("lncrna_count")
    ).join(
        Regulation, Gene.gene_id == Regulation.target_gene_id
    ).join(
        Species, Gene.species_id == Species.species_id
    ).group_by(
        Gene.gene_id,
        Gene.gene_ensembl_id,
        Gene.gene_name,
        Gene.species_id,
        Species.display_name
    )

    # 应用物种过滤
    if species_id:
        query = query.filter(Gene.species_id == species_id)

    # 执行查询并排序
    targets = query.order_by(Gene.gene_name).all()

    # 构建响应
    result = {
        "targets": [
            {
                "gene_id": tgt.gene_id,
                "gene_ensembl_id": tgt.gene_ensembl_id,
                "gene_name": tgt.gene_name,
                "species_id": tgt.species_id,
                "species_name": tgt.species_name,
                "lncrna_count": tgt.lncrna_count
            }
            for tgt in targets
        ]
    }

    # 写入缓存（30 分钟 = 1800 秒）
    cache.set(cache_key, result, 1800)

    return result


def _build_regulation_list_query(db: Session):
    """构建调控关系列表查询的基础部分（使用 LEFT JOIN 获取 target_gene_name）"""
    TargetGene = aliased(Gene, name="target_gene")
    LncRNAGene = aliased(Gene, name="lncrna_gene")

    query = (
        db.query(
            Regulation.regulation_id,
            Regulation.species_id,
            Regulation.lncrna_gene_id,
            Regulation.target_gene_id,
            Regulation.target_chromosome,
            Regulation.target_start,
            Regulation.target_end,
            Regulation.binding_affinity,
            Regulation.best_avg_ba,
            Regulation.num_peaks,
            Species.display_name.label("species_name"),
            LncRNAGene.gene_name.label("lncrna_gene_name"),
            TargetGene.gene_name.label("target_gene_name"),
        )
        .join(Species, Regulation.species_id == Species.species_id)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .outerjoin(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
    )

    return query, LncRNAGene, TargetGene


# Phase 9.15: _parse_ids() 已删除，使用 parse_int_list() 替代
# 详见 app.core.validators.parse_int_list


def _normalize_list_param(value: str | None, *, param_name: str = "parameter") -> str | None:
    """
    规范化列表参数字符串，提升缓存命中率

    - 去除空格
    - 排序元素
    - 重新拼接

    Examples:
        "1, 2, 3" -> "1,2,3"
        "3,1,2" -> "1,2,3"
        "chr1, chr2" -> "chr1,chr2"
    """
    if not value:
        return value

    # SECURITY: 复用统一校验器，限制总长度/项数，避免超长列表导致的 DoS 与缓存键碎片化。
    items = parse_comma_list(value, param_name=param_name)
    if not items:
        return None

    # 尝试按数字排序，失败则按字符串排序
    try:
        items = sorted(items, key=int)
    except ValueError:
        items = sorted(items)
    return ",".join(items)


def _apply_regulation_list_filters(
    query,
    *,
    species_id: Optional[int],
    normalized_species_ids: str | None,
    lncrna_gene_id: Optional[int],
    target_gene_id: Optional[int],
    normalized_lncrna_gene_name: Optional[str],
    normalized_target_gene_name: Optional[str],
    min_ba: Optional[float],
    max_ba: Optional[float],
    normalized_chromosome: Optional[str],
    normalized_chromosomes: str | None,
    lncrna_gene_name_col,
    target_gene_name_col,
    chromosome_col,
):
    if normalized_species_ids:
        parsed_species_ids = parse_int_list(normalized_species_ids, param_name="species_ids", min_value=1, max_value=4)
        if parsed_species_ids:
            query = query.filter(Regulation.species_id.in_(parsed_species_ids))
    elif species_id:
        query = query.filter(Regulation.species_id == species_id)

    if lncrna_gene_id:
        query = query.filter(Regulation.lncrna_gene_id == lncrna_gene_id)
    if target_gene_id:
        query = query.filter(Regulation.target_gene_id == target_gene_id)

    if normalized_lncrna_gene_name:
        escaped = escape_like_pattern(normalized_lncrna_gene_name)
        query = query.filter(lncrna_gene_name_col.ilike(f"%{escaped}%", escape="\\"))

    if normalized_target_gene_name:
        escaped = escape_like_pattern(normalized_target_gene_name)
        query = query.filter(target_gene_name_col.ilike(f"%{escaped}%", escape="\\"))

    if min_ba is not None:
        query = query.filter(Regulation.binding_affinity >= min_ba)
    if max_ba is not None:
        query = query.filter(Regulation.binding_affinity <= max_ba)

    if normalized_chromosomes:
        chrs = parse_comma_list(normalized_chromosomes, param_name="chromosomes")
        if chrs:
            invalid_chrs = [c for c in chrs if not _CHR_PATTERN.match(c)]
            if invalid_chrs:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid chromosome format: {invalid_chrs[:5]}. Expected format: chr1, chr2, ..., chr22, chrX, chrY, chrM"
                )
            query = query.filter(chromosome_col.in_(list({c.lower() for c in chrs})))
    elif normalized_chromosome:
        if not _CHR_PATTERN.match(normalized_chromosome):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid chromosome format: {normalized_chromosome!r}. "
                    "Expected format: chr1, chr2, ..., chr22, chrX, chrY, chrM"
                ),
            )
        query = query.filter(chromosome_col == normalized_chromosome)

    return query


def _build_filtered_regulation_list_queries(
    db: Session,
    *,
    species_id: Optional[int],
    normalized_species_ids: str | None,
    lncrna_gene_id: Optional[int],
    target_gene_id: Optional[int],
    normalized_lncrna_gene_name: Optional[str],
    normalized_target_gene_name: Optional[str],
    min_ba: Optional[float],
    max_ba: Optional[float],
    normalized_chromosome: Optional[str],
    normalized_chromosomes: str | None,
):
    data_query, LncRNAGene, TargetGene = _build_regulation_list_query(db)
    data_query = _apply_regulation_list_filters(
        data_query,
        species_id=species_id,
        normalized_species_ids=normalized_species_ids,
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        normalized_lncrna_gene_name=normalized_lncrna_gene_name,
        normalized_target_gene_name=normalized_target_gene_name,
        min_ba=min_ba,
        max_ba=max_ba,
        normalized_chromosome=normalized_chromosome,
        normalized_chromosomes=normalized_chromosomes,
        lncrna_gene_name_col=LncRNAGene.gene_name,
        target_gene_name_col=TargetGene.gene_name,
        chromosome_col=Regulation.target_chromosome,
    ).order_by(desc(Regulation.binding_affinity), Regulation.regulation_id)

    CountLncRNAGene = aliased(Gene, name="count_lncrna_gene")
    CountTargetGene = aliased(Gene, name="count_target_gene")
    count_query = db.query(Regulation.regulation_id)
    if normalized_lncrna_gene_name:
        count_query = count_query.join(CountLncRNAGene, Regulation.lncrna_gene_id == CountLncRNAGene.gene_id)
    if normalized_target_gene_name:
        count_query = count_query.join(CountTargetGene, Regulation.target_gene_id == CountTargetGene.gene_id)
    count_query = _apply_regulation_list_filters(
        count_query,
        species_id=species_id,
        normalized_species_ids=normalized_species_ids,
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        normalized_lncrna_gene_name=normalized_lncrna_gene_name,
        normalized_target_gene_name=normalized_target_gene_name,
        min_ba=min_ba,
        max_ba=max_ba,
        normalized_chromosome=normalized_chromosome,
        normalized_chromosomes=normalized_chromosomes,
        lncrna_gene_name_col=CountLncRNAGene.gene_name,
        target_gene_name_col=CountTargetGene.gene_name,
        chromosome_col=Regulation.target_chromosome,
    )

    return data_query, count_query


def _build_regulation_list_response(query, *, total: int, page: int, page_size: int) -> PaginatedResponse[RegulationListItem]:
    offset = compute_pagination_offset(page, page_size)
    items = query.offset(offset).limit(page_size).all()

    regulation_list = [
        RegulationListItem(
            regulation_id=item.regulation_id,
            species_id=item.species_id,
            species_name=item.species_name,
            lncrna_gene_id=item.lncrna_gene_id,
            lncrna_gene_name=item.lncrna_gene_name,
            target_gene_id=item.target_gene_id,
            target_gene_name=item.target_gene_name,
            target_chromosome=item.target_chromosome,
            target_start=item.target_start,
            target_end=item.target_end,
            binding_affinity=item.binding_affinity,
            best_avg_ba=item.best_avg_ba,
            num_peaks=item.num_peaks,
        )
        for item in items
    ]

    return PaginatedResponse(
        items=regulation_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get("", response_model=PaginatedResponse[RegulationListItem])
@rate_limit("60/minute")
def list_regulations(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    species_id: Optional[int] = Query(None, ge=1, le=4, description="物种ID（单个）"),
    species_ids: Optional[str] = Query(None, description="物种ID列表（逗号分隔，如: 1,2,3）"),
    lncrna_gene_id: Optional[int] = Query(None, ge=1, description="lncRNA基因ID"),
    target_gene_id: Optional[int] = Query(None, ge=1, description="靶基因ID"),
    lncrna_gene_name: Optional[str] = Query(None, max_length=100, description="lncRNA基因名（模糊搜索）"),
    target_gene_name: Optional[str] = Query(None, max_length=100, description="靶基因名（模糊搜索）"),
    min_ba: Optional[float] = Query(None, ge=0, description="最小结合亲和力"),
    max_ba: Optional[float] = Query(None, ge=0, description="最大结合亲和力"),
    chromosome: Optional[str] = Query(None, max_length=30, description="靶基因染色体（单个）"),
    chromosomes: Optional[str] = Query(None, description="染色体列表（逗号分隔，如: chr1,chr2）"),
    db: Session = Depends(get_db),
):
    """
    获取调控关系列表（支持分页和过滤）

    性能优化：
    - Redis 缓存 15 分钟（TTL 900 秒）
    - 按查询参数组合生成缓存键（使用 make_list_key 进行参数哈希）
    """
    # 规范化列表参数，提升缓存命中率（去空格、排序）
    normalized_species_ids = _normalize_list_param(species_ids, param_name="species_ids")
    normalized_chromosomes = _normalize_list_param(chromosomes, param_name="chromosomes")
    if normalized_chromosomes:
        # Chromosome values are case-insensitive; normalize to reduce cache fragmentation.
        normalized_chromosomes = normalized_chromosomes.lower()
    normalized_lncrna_gene_name = normalize_optional_str(lncrna_gene_name)
    normalized_target_gene_name = normalize_optional_str(target_gene_name)
    normalized_chromosome = normalize_optional_str(chromosome)
    if normalized_chromosome:
        # Chromosome values are case-insensitive; normalize to reduce cache fragmentation.
        normalized_chromosome = normalized_chromosome.lower()

    # 构建缓存键（使用 make_list_key 进行参数哈希，确保键长度稳定且一致）
    cache_key = cache.make_list_key(
        "regulations",
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        species_id=species_id,
        species_ids=normalized_species_ids,
        lncrna_gene_name=normalized_lncrna_gene_name,
        target_gene_name=normalized_target_gene_name,
        min_ba=min_ba,
        max_ba=max_ba,
        chromosome=normalized_chromosome,
        chromosomes=normalized_chromosomes,
        page=page,
        page_size=page_size,
    )

    # 尝试从缓存读取
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("[CACHE HIT] regulations:list")
        return cached

    logger.debug("[CACHE MISS] regulations:list")
    query, count_query = _build_filtered_regulation_list_queries(
        db,
        species_id=species_id,
        normalized_species_ids=normalized_species_ids,
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        normalized_lncrna_gene_name=normalized_lncrna_gene_name,
        normalized_target_gene_name=normalized_target_gene_name,
        min_ba=min_ba,
        max_ba=max_ba,
        normalized_chromosome=normalized_chromosome,
        normalized_chromosomes=normalized_chromosomes,
    )

    # 总数（使用缓存，使用规范化后的参数确保与列表缓存键一致）
    count_cache_key = cache.make_list_key(
        "regulations",
        species_id=species_id,
        species_ids=normalized_species_ids,
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        lncrna_gene_name=normalized_lncrna_gene_name,
        target_gene_name=normalized_target_gene_name,
        min_ba=min_ba,
        max_ba=max_ba,
        chromosome=normalized_chromosome,
        chromosomes=normalized_chromosomes,
    )

    total = cache.get_cached_count(count_query, count_cache_key)
    result = _build_regulation_list_response(query, total=total, page=page, page_size=page_size)

    # 写入缓存（15 分钟 = 900 秒）
    cache.set(cache_key, result, 900)

    return result


@router.get("/{regulation_id}", response_model=RegulationDetail)
@rate_limit("120/minute")
def get_regulation_detail(
    request: Request,
    regulation_id: int,
    db: Session = Depends(get_db),
):
    """
    获取调控关系详细信息（包含序列数据）
    """
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")

    # 使用单次 JOIN 查询获取所有需要的数据
    result = (
        db.query(
            Regulation,
            Species.display_name.label("species_name"),
            LncRNAGene.gene_name.label("lncrna_gene_name"),
            LncRNAGene.gene_ensembl_id.label("lncrna_ensembl_id"),
            TargetGene.gene_name.label("target_gene_name"),
            TargetGene.gene_ensembl_id.label("target_ensembl_id"),
            Sequence.lncrna_sequence,
            Sequence.dna_sequence,
        )
        .join(Species, Regulation.species_id == Species.species_id)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .outerjoin(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .outerjoin(Sequence, Regulation.regulation_id == Sequence.regulation_id)
        .filter(Regulation.regulation_id == regulation_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Regulation not found")

    reg = result[0]

    # 检查序列可用性
    lncrna_seq = result.lncrna_sequence
    dna_seq = result.dna_sequence
    lncrna_available = bool(lncrna_seq and lncrna_seq.strip())
    dna_available = bool(dna_seq and dna_seq.strip())

    # 判断序列不可用的原因
    unavailable_reason = None
    if not dna_available:
        # 检查是否因为位于未定位的 scaffold（random 染色体）
        chr_name = reg.best_peak_chr or ""
        if "_random" in chr_name or "_alt" in chr_name:
            unavailable_reason = f"DNA sequence unavailable: located on unplaced scaffold ({chr_name})"
        else:
            unavailable_reason = "DNA sequence not available in source data"

    return RegulationDetail(
        regulation_id=reg.regulation_id,
        species_id=reg.species_id,
        species_name=result.species_name,
        lncrna_gene_id=reg.lncrna_gene_id,
        lncrna_gene_name=result.lncrna_gene_name,
        lncrna_ensembl_id=result.lncrna_ensembl_id,
        target_gene_id=reg.target_gene_id,
        target_gene_name=result.target_gene_name,
        target_ensembl_id=result.target_ensembl_id,
        target_chromosome=reg.target_chromosome,
        target_start=reg.target_start,
        target_end=reg.target_end,
        tfo_file=reg.tfo_file,
        total_sites=reg.total_sites,
        kept_sites=reg.kept_sites,
        num_peaks=reg.num_peaks,
        best_peak_num=reg.best_peak_num,
        best_avg_ba=reg.best_avg_ba,
        best_num_sites=reg.best_num_sites,
        best_peak_chr=reg.best_peak_chr,
        best_peak_start=reg.best_peak_start,
        best_peak_end=reg.best_peak_end,
        best_site_ba=reg.best_site_ba,
        lncrna_start=reg.lncrna_start,
        lncrna_end=reg.lncrna_end,
        dna_start=reg.dna_start,
        dna_end=reg.dna_end,
        binding_affinity=reg.binding_affinity,
        lncrna_sequence=lncrna_seq,
        dna_sequence=dna_seq,
        lncrna_sequence_available=lncrna_available,
        dna_sequence_available=dna_available,
        sequence_unavailable_reason=unavailable_reason,
    )


@router.get("/gene/{gene_id}", response_model=PaginatedResponse[RegulationListItem])
@rate_limit("60/minute")
def get_gene_regulations(
    request: Request,
    gene_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    min_ba: Optional[float] = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    """
    获取指定基因的所有调控关系（作为lncRNA）
    """
    # 验证基因存在
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    query, LncRNAGene, TargetGene = _build_regulation_list_query(db)
    query = query.filter(Regulation.lncrna_gene_id == gene_id)

    if min_ba is not None:
        query = query.filter(Regulation.binding_affinity >= min_ba)

    # 添加排序，确保分页结果稳定
    query = query.order_by(desc(Regulation.binding_affinity), Regulation.regulation_id)

    # 总数（使用缓存）
    count_cache_key = cache.make_list_key(
        "regulations:gene",
        gene_id=gene_id,
        min_ba=min_ba,
    )
    total = cache.get_cached_count(query, count_cache_key)
    return _build_regulation_list_response(query, total=total, page=page, page_size=page_size)
