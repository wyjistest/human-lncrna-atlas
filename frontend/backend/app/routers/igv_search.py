"""
IGV搜索路由
提供基因搜索、坐标定位和自动完成功能
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Species, Gene
from app.core.utils import escape_like_pattern
from app.schemas.igv import (
    IGVSearchResult,
    GeneAutocompleteItem,
    GeneAutocompleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
def search_genes_for_igv(
    q: str = Query(..., min_length=1, description="搜索关键词（基因名或 Ensembl ID）"),
    species_id: Optional[int] = Query(None, description="物种 ID 过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回结果数量限制"),
    db: Session = Depends(get_db),
):
    """
    IGV 基因搜索 API

    用于物种模式下的基因搜索，返回可在 IGV 中定位的基因列表。
    搜索结果包含基因名、位置信息，可直接用于 IGV 定位。

    Args:
        q: 搜索关键词（支持部分匹配）
        species_id: 可选，限制搜索范围到指定物种
        limit: 返回结果数量限制，默认 20

    Returns:
        匹配的基因列表，包含定位所需的完整信息
    """
    import re

    def escape_like_pattern(value: str) -> str:
        """转义 LIKE 模式中的特殊字符"""
        return re.sub(r'([%_\\])', r'\\\1', value)

    # 构建查询
    query = (
        db.query(
            Gene.gene_id,
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            Gene.species_id,
            Species.display_name.label("species_name"),
        )
        .join(Species, Gene.species_id == Species.species_id)
        .filter(Gene.chromosome.isnot(None))
        .filter(Gene.gene_start.isnot(None))
        .filter(Gene.gene_end.isnot(None))
    )

    # 物种过滤
    if species_id:
        species = db.query(Species).filter(Species.species_id == species_id).first()
        if not species:
            raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")
        query = query.filter(Gene.species_id == species_id)

    # 搜索过滤
    escaped = escape_like_pattern(q)
    search_pattern = f"%{escaped}%"
    query = query.filter(
        (Gene.gene_name.ilike(search_pattern, escape='\\')) |
        (Gene.gene_ensembl_id.ilike(search_pattern, escape='\\'))
    )

    # 排序：精确匹配优先，然后按基因名排序
    # 先按是否精确匹配排序，再按基因名排序
    query = query.order_by(
        # 精确匹配优先
        (Gene.gene_name != q).asc(),
        Gene.gene_name.asc(),
    )

    # 限制结果数量
    results = query.limit(limit).all()

    # 构建响应
    genes = []
    for r in results:
        # 构建 IGV locus 字符串
        locus = f"{r.chromosome}:{r.gene_start}-{r.gene_end}"
        genes.append({
            "gene_id": r.gene_id,
            "gene_name": r.gene_name,
            "gene_ensembl_id": r.gene_ensembl_id,
            "chromosome": r.chromosome,
            "gene_start": r.gene_start,
            "gene_end": r.gene_end,
            "species_id": r.species_id,
            "species_name": r.species_name,
            "locus": locus,
        })

    return {
        "success": True,
        "data": genes,
        "total": len(genes),
        "message": f"Found {len(genes)} genes matching '{q}'" + (f" for species {species_id}" if species_id else ""),
    }


@router.get("/locus")
def search_locus_for_igv(
    q: str = Query(..., min_length=1, description="搜索关键词（基因名、Ensembl ID 或染色体坐标）"),
    species_id: Optional[int] = Query(None, description="物种 ID 过滤"),
    db: Session = Depends(get_db),
):
    """
    IGV.js 兼容的位置搜索 API

    用于 IGV.js 的内置搜索功能，返回单个搜索结果。
    支持：
    1. 基因名搜索（如 CATG00000000034.1）
    2. Ensembl ID 搜索（如 ENSG00000000001）
    3. 染色体坐标搜索（如 chr10:71915113-71916198）

    IGV.js search 配置：
    ```json
    {
        "search": {
            "url": "/api/v1/igv/locus?q=$FEATURE$&species_id=1",
            "chromosomeField": "chromosome",
            "startField": "start",
            "endField": "end"
        }
    }
    ```

    Args:
        q: 搜索关键词
        species_id: 可选，限制搜索范围到指定物种

    Returns:
        IGVSearchResult: IGV.js 期望的搜索结果格式
    """
    import re

    logger.info(f"IGV locus search: q={q}, species_id={species_id}")

    # 1. 首先尝试解析染色体坐标格式
    # 支持格式: chr1:100-200, chr1:100,000-200,000, chrX:1000-2000
    locus_pattern = r'^(chr[0-9XYM]+):([0-9,]+)-([0-9,]+)$'
    locus_match = re.match(locus_pattern, q, re.IGNORECASE)

    if locus_match:
        chromosome = locus_match.group(1)
        # 移除逗号分隔符（如 1,000,000 -> 1000000）
        start = int(locus_match.group(2).replace(',', ''))
        end = int(locus_match.group(3).replace(',', ''))

        logger.info(f"Parsed locus: {chromosome}:{start}-{end}")

        return IGVSearchResult(
            chromosome=chromosome,
            start=start,
            end=end,
            gene=None,
        )

    # 2. 尝试基因名/Ensembl ID 搜索
    def escape_like_pattern(value: str) -> str:
        """转义 LIKE 模式中的特殊字符"""
        return re.sub(r'([%_\\])', r'\\\1', value)

    # 构建基因查询
    query = (
        db.query(
            Gene.gene_name,
            Gene.gene_ensembl_id,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
        )
        .filter(Gene.chromosome.isnot(None))
        .filter(Gene.gene_start.isnot(None))
        .filter(Gene.gene_end.isnot(None))
    )

    # 物种过滤
    if species_id:
        species = db.query(Species).filter(Species.species_id == species_id).first()
        if not species:
            raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")
        query = query.filter(Gene.species_id == species_id)

    # 首先尝试精确匹配
    exact_result = query.filter(
        (Gene.gene_name == q) | (Gene.gene_ensembl_id == q)
    ).first()

    if exact_result:
        logger.info(f"Found exact match: {exact_result.gene_name}")
        return IGVSearchResult(
            chromosome=exact_result.chromosome,
            start=exact_result.gene_start,
            end=exact_result.gene_end,
            gene=exact_result.gene_name or exact_result.gene_ensembl_id,
        )

    # 尝试模糊匹配（前缀匹配优先）
    escaped = escape_like_pattern(q)
    prefix_pattern = f"{escaped}%"

    prefix_result = query.filter(
        (Gene.gene_name.ilike(prefix_pattern, escape='\\')) |
        (Gene.gene_ensembl_id.ilike(prefix_pattern, escape='\\'))
    ).order_by(Gene.gene_name.asc()).first()

    if prefix_result:
        logger.info(f"Found prefix match: {prefix_result.gene_name}")
        return IGVSearchResult(
            chromosome=prefix_result.chromosome,
            start=prefix_result.gene_start,
            end=prefix_result.gene_end,
            gene=prefix_result.gene_name or prefix_result.gene_ensembl_id,
        )

    # 尝试包含匹配
    contains_pattern = f"%{escaped}%"
    contains_result = query.filter(
        (Gene.gene_name.ilike(contains_pattern, escape='\\')) |
        (Gene.gene_ensembl_id.ilike(contains_pattern, escape='\\'))
    ).order_by(Gene.gene_name.asc()).first()

    if contains_result:
        logger.info(f"Found contains match: {contains_result.gene_name}")
        return IGVSearchResult(
            chromosome=contains_result.chromosome,
            start=contains_result.gene_start,
            end=contains_result.gene_end,
            gene=contains_result.gene_name or contains_result.gene_ensembl_id,
        )

    # 未找到任何匹配
    logger.warning(f"No match found for: {q}")
    raise HTTPException(
        status_code=404,
        detail=f"No gene or locus found matching '{q}'"
    )


@router.get("/autocomplete", response_model=GeneAutocompleteResponse)
def autocomplete_genes(
    q: str = Query(..., min_length=1, description="搜索关键词（基因名前缀）"),
    species_id: Optional[int] = Query(None, description="物种 ID 过滤"),
    limit: int = Query(10, ge=1, le=50, description="返回结果数量限制"),
    db: Session = Depends(get_db),
):
    """
    基因自动补全搜索 API

    用于 IGV 搜索框的下拉列表，当用户输入 "hla-" 时返回所有匹配的基因供选择。

    搜索逻辑：
    1. 优先前缀匹配（LIKE 'keyword%'）
    2. 如果前缀匹配结果不足，补充包含匹配（LIKE '%keyword%'）
    3. 大小写不敏感
    4. 精确匹配的结果排在最前

    Args:
        q: 搜索关键词（支持部分匹配）
        species_id: 可选，限制搜索范围到指定物种
        limit: 返回结果数量限制，默认 10，最大 50

    Returns:
        匹配的基因列表，包含基因名、染色体、位置、物种信息
    """
    import re

    def escape_like_pattern(value: str) -> str:
        """转义 LIKE 模式中的特殊字符"""
        return re.sub(r'([%_\\])', r'\\\1', value)

    logger.info(f"Gene autocomplete: q={q}, species_id={species_id}, limit={limit}")

    # 构建基础查询
    base_query = (
        db.query(
            Gene.gene_name,
            Gene.chromosome,
            Gene.gene_start,
            Gene.gene_end,
            Gene.species_id,
        )
        .filter(Gene.chromosome.isnot(None))
        .filter(Gene.gene_start.isnot(None))
        .filter(Gene.gene_end.isnot(None))
        .filter(Gene.gene_name.isnot(None))
    )

    # 物种过滤
    if species_id:
        species = db.query(Species).filter(Species.species_id == species_id).first()
        if not species:
            raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")
        base_query = base_query.filter(Gene.species_id == species_id)

    # 转义搜索关键词
    escaped = escape_like_pattern(q)

    # 收集结果（使用集合去重）
    results = []
    seen_genes = set()

    # 1. 精确匹配优先
    exact_results = base_query.filter(
        Gene.gene_name.ilike(escaped, escape='\\')
    ).limit(limit).all()

    for r in exact_results:
        key = (r.gene_name, r.species_id)
        if key not in seen_genes:
            seen_genes.add(key)
            results.append(r)

    # 2. 前缀匹配
    if len(results) < limit:
        prefix_pattern = f"{escaped}%"
        prefix_results = base_query.filter(
            Gene.gene_name.ilike(prefix_pattern, escape='\\')
        ).order_by(Gene.gene_name.asc()).limit(limit).all()

        for r in prefix_results:
            if len(results) >= limit:
                break
            key = (r.gene_name, r.species_id)
            if key not in seen_genes:
                seen_genes.add(key)
                results.append(r)

    # 3. 包含匹配作为后备
    if len(results) < limit:
        contains_pattern = f"%{escaped}%"
        contains_results = base_query.filter(
            Gene.gene_name.ilike(contains_pattern, escape='\\')
        ).order_by(Gene.gene_name.asc()).limit(limit * 2).all()

        for r in contains_results:
            if len(results) >= limit:
                break
            key = (r.gene_name, r.species_id)
            if key not in seen_genes:
                seen_genes.add(key)
                results.append(r)

    # 构建响应
    data = [
        GeneAutocompleteItem(
            gene_name=r.gene_name,
            chromosome=r.chromosome,
            start=r.gene_start,
            end=r.gene_end,
            species_id=r.species_id,
        )
        for r in results
    ]

    logger.info(f"Autocomplete found {len(data)} results for '{q}'")

    return GeneAutocompleteResponse(
        success=True,
        data=data,
    )
