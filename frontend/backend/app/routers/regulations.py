"""调控关系API路由"""
import logging
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, aliased
from sqlalchemy import desc
from math import ceil


def escape_like_pattern(value: str) -> str:
    """转义 LIKE 模式中的特殊字符 (%, _, \\)"""
    return re.sub(r'([%_\\])', r'\\\1', value)

from app.core.database import get_db
from app.models import Regulation, Gene, Species, Sequence
from app.schemas.regulation import (
    RegulationDetail,
    RegulationListItem,
)
from app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regulations", tags=["regulations"])


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


def _parse_ids(ids_str: str, param_name: str) -> list[int]:
    """解析逗号分隔的 ID 字符串，返回整数列表"""
    result = []
    for x in ids_str.split(","):
        x = x.strip()
        if x:
            try:
                result.append(int(x))
            except ValueError:
                logger.warning(f"Invalid {param_name} value: {x}")
    return result


@router.get("", response_model=PaginatedResponse[RegulationListItem])
def list_regulations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    species_id: Optional[int] = Query(None, description="物种ID（单个）"),
    species_ids: Optional[str] = Query(None, description="物种ID列表（逗号分隔，如: 1,2,3）"),
    lncrna_gene_id: Optional[int] = Query(None, description="lncRNA基因ID"),
    target_gene_id: Optional[int] = Query(None, description="靶基因ID"),
    lncrna_gene_name: Optional[str] = Query(None, description="lncRNA基因名（模糊搜索）"),
    target_gene_name: Optional[str] = Query(None, description="靶基因名（模糊搜索）"),
    min_ba: Optional[float] = Query(None, ge=0, description="最小结合亲和力"),
    max_ba: Optional[float] = Query(None, ge=0, description="最大结合亲和力"),
    chromosome: Optional[str] = Query(None, description="靶基因染色体（单个）"),
    chromosomes: Optional[str] = Query(None, description="染色体列表（逗号分隔，如: chr1,chr2）"),
    db: Session = Depends(get_db),
):
    """
    获取调控关系列表（支持分页和过滤）
    """
    query, LncRNAGene, TargetGene = _build_regulation_list_query(db)

    # 物种筛选：优先使用数组参数
    if species_ids:
        ids = _parse_ids(species_ids, "species_ids")
        if ids:
            query = query.filter(Regulation.species_id.in_(ids))
    elif species_id:
        query = query.filter(Regulation.species_id == species_id)

    if lncrna_gene_id:
        query = query.filter(Regulation.lncrna_gene_id == lncrna_gene_id)
    if target_gene_id:
        query = query.filter(Regulation.target_gene_id == target_gene_id)

    # lncRNA基因名模糊搜索（转义特殊字符防止意外匹配）
    if lncrna_gene_name:
        escaped = escape_like_pattern(lncrna_gene_name)
        query = query.filter(LncRNAGene.gene_name.ilike(f"%{escaped}%", escape='\\'))

    # 靶基因名模糊搜索（转义特殊字符防止意外匹配）
    if target_gene_name:
        escaped = escape_like_pattern(target_gene_name)
        query = query.filter(TargetGene.gene_name.ilike(f"%{escaped}%", escape='\\'))

    # BA范围筛选
    if min_ba is not None:
        query = query.filter(Regulation.binding_affinity >= min_ba)
    if max_ba is not None:
        query = query.filter(Regulation.binding_affinity <= max_ba)

    # 染色体筛选：优先使用数组参数
    if chromosomes:
        chrs = [x.strip() for x in chromosomes.split(",") if x.strip()]
        if chrs:
            query = query.filter(Regulation.target_chromosome.in_(chrs))
    elif chromosome:
        query = query.filter(Regulation.target_chromosome == chromosome)

    # 添加排序，确保分页结果稳定
    query = query.order_by(desc(Regulation.binding_affinity), Regulation.regulation_id)

    # 总数
    total = query.count()

    # 分页
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    # 转换为响应模型
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


@router.get("/{regulation_id}", response_model=RegulationDetail)
def get_regulation_detail(
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
def get_gene_regulations(
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

    # 总数
    total = query.count()

    # 分页
    offset = (page - 1) * page_size
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
