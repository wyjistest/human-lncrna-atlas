"""数据导出 API 路由

Phase 6.0-A: 为 Jupyter Notebook 数据分析提供便捷的数据导出 API

支持格式:
- JSON (默认)
- CSV (逗号分隔) - 真流式输出，内存占用 O(1)
- Excel (.xlsx) - write_only 模式，减少内存峰值
- JSONL (Phase 9.11) - 流式 JSON Lines，避免大数据集内存峰值

性能优化:
- 使用 LIMIT 限制返回数量（最大 50000）
- 真流式响应：逐行生成 CSV/JSONL，不在内存中保存完整数据集
- 复用数据库连接池

Phase 9.3 改进：
- CR-005: 修复伪流式输出问题，改用生成器逐行 yield

Phase 9.11 改进：
- 添加 JSONL 流式输出格式，解决 JSON 导出内存峰值问题
"""
import logging
from typing import List, Optional, Dict, Any, Iterator, Generator, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Float, cast, select, text
from sqlalchemy.orm import Session, aliased
		
from app.core.database import get_db
from app.core.utils import escape_like_pattern, sanitize_for_log
from app.core.validators import (
    MAX_EXPORT_MARKS,
    MAX_ITEM_LENGTH,
    MAX_JSON_EXPORT_LIMIT,
    parse_int_list,
    parse_comma_list,
)
from app.models import Gene, Regulation, Species, Trait, TraitGeneAssociation
from app.routers.chipseq_rate_limit import rate_limit
from app.schemas.export import (
    HighAffinityExportResponse,
    ConservationExportResponse,
    ChipseqOverlapExportResponse,
    DiseaseNetworkExportResponse,
    NetworkNode,
    NetworkEdge,
    RegulationsExportResponse,
)
from app.utils.streaming_export import (
    stream_csv_response,
    stream_excel_response,
    stream_jsonl_response,
    create_db_row_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])

# 最大导出数量限制（防止内存溢出）
MAX_EXPORT_LIMIT = 50000  # CSV/Excel/JSONL 流式输出可支持大数据集
# Backward-compat constant (tests/imports rely on this name)
MAX_JSON_LIMIT = MAX_JSON_EXPORT_LIMIT  # JSON 模式全量加载进内存，限制为 5000 条


def _apply_json_memory_limit(request: Request, limit: int, output_format: str) -> int:
    """
    Enforce JSON in-memory limits consistently across export endpoints.

    Policy:
    - If user explicitly provides `limit` and it exceeds MAX_JSON_LIMIT: raise 400 (prevents DoS).
    - If `limit` is implicit (default) and exceeds MAX_JSON_LIMIT: auto-cap to MAX_JSON_LIMIT.
      This avoids breaking callers that omit `limit` while still protecting memory.
    """
    if output_format != "json" or limit <= MAX_JSON_LIMIT:
        return limit

    # FastAPI 解析后无法直接判断是否使用了默认值，这里用原始 query_params 作为信号。
    limit_was_explicit = "limit" in request.query_params
    if limit_was_explicit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"JSON format is limited to {MAX_JSON_LIMIT} records due to memory constraints. "
                f"For larger datasets, please use 'jsonl' (JSON Lines) format which supports up to {MAX_EXPORT_LIMIT} records."
            ),
        )

    logger.warning(
        "[EXPORT] %s: JSON limit capped to %s (requested default: %s). Use jsonl/csv/excel for larger exports.",
        request.url.path,
        MAX_JSON_LIMIT,
        limit,
    )
    return MAX_JSON_LIMIT


def _execute_streaming(db: Session, stmt, params: Optional[Dict[str, Any]] = None):
    """
    Execute a SQLAlchemy statement with streaming-friendly execution options.

    Motivation:
    - StreamingResponse + large exports can otherwise cause DBAPI drivers to buffer
      large result sets, increasing memory pressure and DoS risk.
    - This helper keeps behavior unchanged for JSON (in-memory) paths by only being
      used in csv/excel/jsonl branches.
    """
    executable = stmt.execution_options(stream_results=True)
    if params is not None:
        return db.execute(executable, params)
    return db.execute(executable)


def is_effective_like_filter(value: Optional[str]) -> bool:
    """
    判断 LIKE 过滤条件是否有效（能有效缩小结果集）。

    无效情况：
    - None 或空字符串
    - 纯空白字符
    - 纯通配符（如 '%', '%%', '_', '%_', '___' 等）

    转义后再判断：如果输入是 'dia%betes' 这种混合值，
    转义后是 'dia\\%betes'，包含非通配符字符，是有效过滤。
    """
    if not value or not value.strip():
        return False

    # 移除所有 LIKE 通配符后检查是否还有内容
    stripped = value.replace('%', '').replace('_', '').strip()
    return len(stripped) > 0


def _validate_mark_names_list(mark_names: List[str]) -> List[str]:
    """
    Validate mark_names list query param for /export/chipseq-overlaps.

    Security/Perf:
    - Prevent parameter amplification DoS via extremely large repeated query params.
    - Enforce per-item length limits consistent with app.core.validators.
    """
    if not mark_names:
        raise HTTPException(status_code=400, detail="At least one mark_name is required")

    if len(mark_names) > MAX_EXPORT_MARKS:
        raise HTTPException(
            status_code=400,
            detail=f"mark_names: Maximum {MAX_EXPORT_MARKS} items allowed, got {len(mark_names)}",
        )

    normalized: List[str] = []
    for idx, raw in enumerate(mark_names):
        item = str(raw).strip() if raw is not None else ""
        if not item:
            continue
        if len(item) > MAX_ITEM_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"mark_names[{idx}]: Item too long, maximum {MAX_ITEM_LENGTH} characters",
            )
        normalized.append(item)

    if not normalized:
        raise HTTPException(status_code=400, detail="At least one mark_name is required")

    return normalized


def export_to_streaming_format(
    row_iterator: Iterator[Dict[str, Any]],
    fieldnames: List[str],
    output_format: str,
    filename: str,
    *,
    array_fields: Optional[List[str]] = None,
):
    """
    将数据导出为指定格式（真流式输出）

    Args:
        row_iterator: 数据行迭代器（生成器）
        fieldnames: 列名列表
        output_format: 导出格式 (csv/excel)
        filename: 文件名（不含扩展名）
        array_fields: 需要转换为逗号分隔字符串的数组字段

    Returns:
        StreamingResponse

    Note:
        JSON 格式不使用此函数，直接返回 Pydantic 响应模型
    """
    # 可选：转换数组字段为字符串（仅用于 CSV/Excel，JSONL 保持数组原样）
    def transform_arrays(row: Dict[str, Any]) -> Dict[str, Any]:
        if array_fields:
            for field in array_fields:
                if field in row and isinstance(row[field], (list, tuple)):
                    row[field] = ", ".join(str(v) for v in row[field] if v is not None)
        return row

    # 包装迭代器以应用转换（仅用于 CSV/Excel）
    def transformed_rows() -> Generator[Dict[str, Any], None, None]:
        for row in row_iterator:
            yield transform_arrays(row)

    # 原始行迭代器（用于 JSONL，保持数组结构）
    def raw_rows() -> Generator[Dict[str, Any], None, None]:
        for row in row_iterator:
            yield row

    if output_format == "csv":
        return stream_csv_response(
            transformed_rows(),
            fieldnames,
            f"{filename}.csv",
        )

    elif output_format == "excel":
        return stream_excel_response(
            transformed_rows(),
            fieldnames,
            f"{filename}.xlsx",
        )

    elif output_format == "jsonl":
        # Phase 9.11: JSONL 流式输出，保持数组原样（不扁平化）
        return stream_jsonl_response(
            raw_rows(),
            f"{filename}.jsonl",
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {output_format}")


def build_regulations_export_stmt(
    *,
    min_ba: Optional[float],
    max_ba: Optional[float],
    species_id_list: Optional[List[int]],
    chromosome_list: Optional[List[str]],
    lncrna_gene_name: Optional[str],
    target_gene_name: Optional[str],
    limit: int,
):
    """
    构建 regulations 导出查询（SQLAlchemy 表达式）。

    目的：
    - 替代动态 SQL 字符串拼接，降低维护与注入风险
    - 统一参数化与 LIKE 转义策略（防止通配符绕过导致全表扫描）
    """
    lnc = aliased(Gene)
    tgt = aliased(Gene)

    stmt = (
        select(
            Regulation.regulation_id,
            lnc.gene_name.label("lncrna_gene_name"),
            tgt.gene_name.label("target_gene_name"),
            Species.display_name.label("species_name"),
            Regulation.target_chromosome,
            Regulation.target_start,
            Regulation.target_end,
            cast(Regulation.binding_affinity, Float).label("binding_affinity"),
            Regulation.num_peaks,
        )
        .select_from(Regulation)
        .join(lnc, Regulation.lncrna_gene_id == lnc.gene_id)
        .join(tgt, Regulation.target_gene_id == tgt.gene_id)
        .join(Species, Regulation.species_id == Species.species_id)
    )

    if min_ba is not None:
        stmt = stmt.where(Regulation.binding_affinity >= min_ba)
    if max_ba is not None:
        stmt = stmt.where(Regulation.binding_affinity <= max_ba)

    if species_id_list:
        stmt = stmt.where(Regulation.species_id.in_(species_id_list))

    if chromosome_list:
        stmt = stmt.where(Regulation.target_chromosome.in_(chromosome_list))

    if lncrna_gene_name and lncrna_gene_name.strip():
        pattern = f"%{escape_like_pattern(lncrna_gene_name.strip())}%"
        stmt = stmt.where(lnc.gene_name.ilike(pattern, escape="\\"))

    if target_gene_name and target_gene_name.strip():
        pattern = f"%{escape_like_pattern(target_gene_name.strip())}%"
        stmt = stmt.where(tgt.gene_name.ilike(pattern, escape="\\"))

    return stmt.order_by(Regulation.binding_affinity.desc().nullslast()).limit(limit)


# ============================================================================
# 1. High-Affinity Export
# ============================================================================

@router.get("/high-affinity", response_model=HighAffinityExportResponse)
@rate_limit("5/minute")
def export_high_affinity(
    request: Request,
    min_ba: float = Query(100.0, ge=0, description="最小结合亲和力 (BA)"),
    species_id: Optional[int] = Query(None, ge=1, le=4, description="物种 ID 筛选 (1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴)"),
    limit: int = Query(10000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    output_format: Literal["json", "csv", "excel", "jsonl"] = Query("json", alias="format", description="导出格式 (json/csv/excel/jsonl)"),
    db: Session = Depends(get_db),
):
    """
    导出高亲和力调控关系数据（用于网络分析）

    **应用场景**:
    - 构建 lncRNA-target 调控网络
    - 筛选强调控关系（BA > 阈值）
    - 跨物种比较分析

    **返回字段**:
    - lncrna_gene_id/name: lncRNA 基因 ID 和名称
    - target_gene_id/name: 靶基因 ID 和名称
    - binding_affinity: 结合亲和力
    - species_id/name: 物种信息
    - chr/start/end: 基因组位置

    **性能**: 10000 条记录 < 5s
    **内存**: CSV 真流式 O(1)；Excel 使用 write_only 模式降低内存峰值
    """
    logger.info(
        "[EXPORT] high-affinity: min_ba=%s, species_id=%s, limit=%s, output_format=%s",
        min_ba,
        species_id,
        limit,
        output_format,
    )

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    # JSON 模式独立限制（防止内存峰值）；默认 limit 过大时自动降级到 MAX_JSON_LIMIT
    limit = _apply_json_memory_limit(request, limit, output_format)

    lnc = aliased(Gene)
    tgt = aliased(Gene)

    stmt = (
        select(
            Regulation.lncrna_gene_id,
            lnc.gene_name.label("lncrna_name"),
            Regulation.target_gene_id,
            tgt.gene_name.label("target_name"),
            cast(Regulation.binding_affinity, Float).label("binding_affinity"),
            Regulation.species_id,
            Species.display_name.label("species_name"),
            Regulation.target_chromosome.label("chr"),
            Regulation.target_start.label("start_in_genome"),
            Regulation.target_end.label("end_in_genome"),
        )
        .select_from(Regulation)
        .join(lnc, Regulation.lncrna_gene_id == lnc.gene_id)
        .join(tgt, Regulation.target_gene_id == tgt.gene_id)
        .join(Species, Regulation.species_id == Species.species_id)
        .where(Regulation.binding_affinity >= min_ba)
    )
    if species_id is not None:
        stmt = stmt.where(Regulation.species_id == species_id)
    stmt = stmt.order_by(Regulation.binding_affinity.desc().nullslast()).limit(limit)

    # 定义列名（用于流式导出）
    fieldnames = [
        "lncrna_gene_id", "lncrna_name", "target_gene_id", "target_name",
        "binding_affinity", "species_id", "species_name", "chr",
        "start_in_genome", "end_in_genome"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = _execute_streaming(db, stmt)
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            output_format,
            "high_affinity_regulations",
        )

    # JSON: 标准响应（需要 total 字段）
    result = db.execute(stmt)
    data = [dict(row._mapping) for row in result]

    query_params = {
        "min_ba": min_ba,
        "species_id": species_id,
        "limit": limit,
        "format": output_format
    }

    return HighAffinityExportResponse(
        data=data,
        total=len(data),
        query_params=query_params
    )


# ============================================================================
# 2. Conservation Export
# ============================================================================

@router.get("/conservation", response_model=ConservationExportResponse)
@rate_limit("5/minute")
def export_conservation(
    request: Request,
    min_species_count: int = Query(2, ge=1, le=4, description="最少保守物种数"),
    limit: int = Query(5000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    output_format: Literal["json", "csv", "excel", "jsonl"] = Query("json", alias="format", description="导出格式 (json/csv/excel/jsonl)"),
    db: Session = Depends(get_db),
):
    """
    导出跨物种保守 lncRNA 及其调控关系

    **应用场景**:
    - 鉴定功能保守的 lncRNA
    - 研究跨物种调控机制
    - 进化保守性分析

    **返回字段**:
    - core_id: 核心基因 ID
    - lncrna_names: 各物种 lncRNA 名称列表
    - species_count: 保守物种数
    - total_regulations: 总调控关系数
    - avg_binding_affinity: 平均结合亲和力
    - conserved_targets: 保守靶基因列表（取前10个）

    **性能**: 5000 条记录 < 3s
    **内存**: CSV 真流式 O(1)；Excel 使用 write_only 模式降低内存峰值
    """
    logger.info(
        "[EXPORT] conservation: min_species_count=%s, limit=%s, output_format=%s",
        min_species_count,
        limit,
        output_format,
    )

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    # JSON 模式独立限制（防止内存峰值）；默认 limit 过大时自动降级到 MAX_JSON_LIMIT
    limit = _apply_json_memory_limit(request, limit, output_format)

    # 查询保守 lncRNA 统计信息
    sql = text("""
        SELECT
            g.core_id,
            COUNT(DISTINCT g.species_id) as species_count,
            COUNT(DISTINCT r.regulation_id) as total_regulations,
            AVG(r.binding_affinity) as avg_binding_affinity,
            ARRAY_AGG(DISTINCT g.gene_name) as lncrna_names,
            ARRAY_AGG(DISTINCT tgt.gene_name) FILTER (WHERE tgt.gene_name IS NOT NULL) as target_names
        FROM genes g
        JOIN regulations r ON g.gene_id = r.lncrna_gene_id
        LEFT JOIN genes tgt ON r.target_gene_id = tgt.gene_id
        WHERE g.core_id IS NOT NULL
        GROUP BY g.core_id
        HAVING COUNT(DISTINCT g.species_id) >= :min_species_count
        ORDER BY species_count DESC, total_regulations DESC
        LIMIT :limit
    """)

    # 行转换函数：处理数组字段和限制靶基因数量
    def transform_conservation_row(row: Dict[str, Any]) -> Dict[str, Any]:
        conserved_targets = row.get("target_names", []) or []
        row["conserved_targets"] = conserved_targets[:10] if conserved_targets else []
        row.pop("target_names", None)
        return row

    # 定义列名
    fieldnames = [
        "core_id", "species_count", "total_regulations",
        "avg_binding_affinity", "lncrna_names", "conserved_targets"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = _execute_streaming(db, sql, {
            "min_species_count": min_species_count,
            "limit": limit
        })
        return export_to_streaming_format(
            create_db_row_generator(result, transform=transform_conservation_row),
            fieldnames,
            output_format,
            "conservation_lncrnas",
            array_fields=["lncrna_names", "conserved_targets"],
        )

    # JSON: 标准响应
    result = db.execute(sql, {
        "min_species_count": min_species_count,
        "limit": limit
    })
    data = [transform_conservation_row(dict(row._mapping)) for row in result]

    query_params = {
        "min_species_count": min_species_count,
        "limit": limit,
        "format": output_format
    }

    return ConservationExportResponse(
        data=data,
        total=len(data),
        query_params=query_params
    )


# ============================================================================
# 3. ChIP-seq Overlap Export
# ============================================================================

@router.get("/chipseq-overlaps", response_model=ChipseqOverlapExportResponse)
@rate_limit("5/minute")
def export_chipseq_overlaps(
    request: Request,
    mark_names: List[str] = Query(
        default=["H3K4me3", "H3K27me3"],
        description="组蛋白标记列表（支持多个，如 H3K4me3, H3K27me3, H3K27ac）"
    ),
    min_ba: float = Query(100.0, ge=0, description="最小结合亲和力"),
    limit: int = Query(10000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    output_format: Literal["json", "csv", "excel", "jsonl"] = Query("json", alias="format", description="导出格式 (json/csv/excel/jsonl)"),
    db: Session = Depends(get_db),
):
    """
    导出调控位点与 ChIP-seq 峰的重叠数据（表观遗传标记）

    **应用场景**:
    - 研究 lncRNA 与组蛋白修饰的关联
    - 表观遗传调控机制分析
    - 染色质状态预测

    **常用组蛋白标记**:
    - H3K4me3: 活跃启动子标记
    - H3K27me3: 沉默标记（Polycomb 抑制）
    - H3K27ac: 活跃增强子标记
    - H3K9me3: 异染色质标记
    - H3K36me3: 活跃转录区标记

    **返回字段**:
    - regulation_id: 调控关系 ID
    - lncrna_name/target_name: 基因名称
    - binding_affinity: 结合亲和力
    - mark_name: 组蛋白标记类型
    - peak_score: ChIP-seq 峰得分
    - peak_chr/start/end: 峰位置
    - cell_type: 细胞类型

    **性能**: 10000 条记录 < 5s（使用物化视图 mv_lncrna_chipseq_overlaps）
    **内存**: CSV 真流式 O(1)；Excel 使用 write_only 模式降低内存峰值
    """
    # Validate early to avoid logging/processing extremely large query parameter lists.
    mark_names = _validate_mark_names_list(mark_names)

    logger.info(
        "[EXPORT] chipseq-overlaps: mark_names=%s, min_ba=%s, limit=%s, output_format=%s",
        sanitize_for_log(mark_names, max_length=500),
        min_ba,
        limit,
        output_format,
    )

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    # JSON 模式独立限制（防止内存峰值）；默认 limit 过大时自动降级到 MAX_JSON_LIMIT
    limit = _apply_json_memory_limit(request, limit, output_format)

    # 使用物化视图查询（性能优化）
    # NOTE: mv_lncrna_chipseq_overlaps 已经做了必要的反范式化（gene_name / mark_name / binding_affinity 等），
    # 这里避免额外 JOIN，减少 6M+ 行大表的 join 代价与 planner 复杂度。
    sql = text("""
        SELECT
            o.regulation_id,
            o.lncrna_name as lncrna_name,
            o.target_gene_name as target_name,
            o.binding_affinity,
            o.mark_name,
            o.fold_enrichment as peak_score,
            o.chromosome as peak_chr,
            o.peak_start,
            o.peak_end,
            o.cell_type
        FROM mv_lncrna_chipseq_overlaps o
        WHERE o.mark_name = ANY(:mark_names)
          AND o.binding_affinity >= :min_ba
        ORDER BY o.binding_affinity DESC, o.fold_enrichment DESC
        LIMIT :limit
    """)

    # 定义列名
    fieldnames = [
        "regulation_id", "lncrna_name", "target_name", "binding_affinity",
        "mark_name", "peak_score", "peak_chr", "peak_start", "peak_end", "cell_type"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = _execute_streaming(db, sql, {
            "mark_names": mark_names,
            "min_ba": min_ba,
            "limit": limit
        })
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            output_format,
            "chipseq_overlaps",
        )

    # JSON: 标准响应
    result = db.execute(sql, {
        "mark_names": mark_names,
        "min_ba": min_ba,
        "limit": limit
    })
    data = [dict(row._mapping) for row in result]

    query_params = {
        "mark_names": mark_names,
        "min_ba": min_ba,
        "limit": limit,
        "format": output_format
    }

    return ChipseqOverlapExportResponse(
        data=data,
        total=len(data),
        query_params=query_params
    )


# ============================================================================
# 4. Disease Network Export
# ============================================================================

@router.get("/disease-network", response_model=DiseaseNetworkExportResponse)
@rate_limit("5/minute")
def export_disease_network(
    request: Request,
    trait_name: Optional[str] = Query(
        None,
        description="疾病/性状名称（模糊搜索，如 'diabetes', 'cancer'）"
    ),
    limit: int = Query(5000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回边数"),
    output_format: Literal["json"] = Query("json", alias="format", description="导出格式 (仅支持 json，网络数据不适合 CSV)"),
    db: Session = Depends(get_db),
):
    """
    导出疾病-基因-lncRNA 三层网络数据（用于 Cytoscape/igraph）

    **应用场景**:
    - 疾病相关 lncRNA 网络可视化
    - GWAS 关联基因分析
    - 疾病调控通路研究

    **网络结构**:
    - 节点类型: disease (疾病), gene (靶基因), lncrna (调控基因)
    - 边类型: disease-gene (GWAS 关联), regulation (调控关系)
    - 边权重: p-value (疾病关联) / BA (调控亲和力)

    **返回格式**:
    ```json
    {
      "nodes": [
        {"id": "disease_1", "type": "disease", "name": "Type 2 Diabetes"},
        {"id": "gene_456", "type": "gene", "name": "TP53"},
        {"id": "lncrna_123", "type": "lncrna", "name": "MALAT1"}
      ],
      "edges": [
        {"source": "disease_1", "target": "gene_456", "type": "disease-gene", "weight": 1e-8},
        {"source": "gene_456", "target": "lncrna_123", "type": "regulation", "weight": 150.5}
      ]
    }
    ```

    **导入 Cytoscape**:
    ```python
    import os
    import requests

    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    data = requests.get(
        f"{api_base_url}/api/v1/export/disease-network",
        params={"trait_name": "diabetes"},
    ).json()
    # 使用 py4cytoscape 导入
    ```

    **性能**: 5000 条边 < 5s
    """
    logger.info(
        "[EXPORT] disease-network: trait_name=%s, limit=%s, output_format=%s",
        sanitize_for_log(trait_name, max_length=200),
        limit,
        output_format,
    )

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    if output_format != "json":
        raise HTTPException(
            status_code=400,
            detail="Disease network export only supports JSON format (network data structure)"
        )

    # P0 修复：防止无过滤条件的全表扫描
    # 当未提供有效 trait_name 过滤时，限制返回数量以避免内存溢出
    # 注意：空字符串、纯通配符（%、_）都视为未提供有效过滤，防止绕过保护
    # Phase 9.13: 使用 is_effective_like_filter 检测通配符绕过攻击
    if not is_effective_like_filter(trait_name):
        effective_limit = min(limit, 500)  # 无过滤时最多返回 500 条
        logger.warning(
            "[EXPORT] disease-network: No effective trait_name filter provided (value=%s), "
            "limiting to %s rows (requested: %s)",
            sanitize_for_log(trait_name, max_length=200),
            effective_limit,
            limit,
        )
        # 无效过滤时传递 None，避免纯通配符查询
        escaped_trait_name = None
    else:
        effective_limit = limit
        # 转义 trait_name 防止通配符注入
        escaped_trait_name = escape_like_pattern(trait_name)

    nodes = []
    edges = []
    node_ids = set()

    # ========================================================================
    # Step 1: 查询疾病-基因边
    # ========================================================================
    disease_gene_stmt = (
        select(
            Trait.trait_name,
            Trait.trait_id,
            Gene.gene_id,
            Gene.gene_name,
            TraitGeneAssociation.trait_snp_pvalue.label("pvalue"),
        )
        .select_from(TraitGeneAssociation)
        .join(Trait, TraitGeneAssociation.trait_id == Trait.trait_id)
        .join(Gene, TraitGeneAssociation.core_id == Gene.core_id)
        .limit(effective_limit)
    )
    if escaped_trait_name:
        pattern = f"%{escaped_trait_name}%"
        disease_gene_stmt = disease_gene_stmt.where(Trait.trait_name.ilike(pattern, escape="\\"))

    disease_gene_result = db.execute(disease_gene_stmt)

    # 收集基因 ID（用于后续查询调控关系）
    gene_ids = set()
    trait_ids_seen = set()

    for row in disease_gene_result:
        trait_id = row.trait_id
        trait_name_val = row.trait_name
        gene_id = row.gene_id
        gene_name = row.gene_name
        pvalue = float(row.pvalue) if row.pvalue else None

        # 添加疾病节点
        disease_node_id = f"disease_{trait_id}"
        if disease_node_id not in node_ids:
            nodes.append(NetworkNode(
                id=disease_node_id,
                type="disease",
                name=trait_name_val
            ))
            node_ids.add(disease_node_id)
            trait_ids_seen.add(trait_id)

        # 添加基因节点
        gene_node_id = f"gene_{gene_id}"
        if gene_node_id not in node_ids:
            nodes.append(NetworkNode(
                id=gene_node_id,
                type="gene",
                name=gene_name
            ))
            node_ids.add(gene_node_id)
            gene_ids.add(gene_id)

        # 添加疾病-基因边
        edges.append(NetworkEdge(
            source=disease_node_id,
            target=gene_node_id,
            type="disease-gene",
            weight=pvalue
        ))

    # ========================================================================
    # Step 2: 查询基因-lncRNA 边（调控关系）
    # ========================================================================
    if gene_ids:
        gene_lncrna_sql = text("""
            SELECT
                r.target_gene_id,
                tgt.gene_name as target_name,
                r.lncrna_gene_id,
                lnc.gene_name as lncrna_name,
                r.binding_affinity
            FROM regulations r
            JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
            JOIN genes tgt ON r.target_gene_id = tgt.gene_id
            WHERE r.target_gene_id = ANY(:gene_ids)
            ORDER BY r.binding_affinity DESC
            LIMIT :limit
        """)

        gene_lncrna_result = db.execute(gene_lncrna_sql, {
            "gene_ids": list(gene_ids),
            "limit": effective_limit
        })

        for row in gene_lncrna_result:
            target_gene_id = row.target_gene_id
            lncrna_gene_id = row.lncrna_gene_id
            lncrna_name = row.lncrna_name
            binding_affinity = float(row.binding_affinity) if row.binding_affinity else None

            # 添加 lncRNA 节点
            lncrna_node_id = f"lncrna_{lncrna_gene_id}"
            if lncrna_node_id not in node_ids:
                nodes.append(NetworkNode(
                    id=lncrna_node_id,
                    type="lncrna",
                    name=lncrna_name
                ))
                node_ids.add(lncrna_node_id)

            # 添加基因-lncRNA 边（注意方向：lncrna -> gene）
            edges.append(NetworkEdge(
                source=lncrna_node_id,
                target=f"gene_{target_gene_id}",
                type="regulation",
                weight=binding_affinity
            ))

    query_params = {
        "trait_name": trait_name,
        "limit": limit,
        "format": output_format
    }

    logger.info(f"[EXPORT] disease-network: {len(nodes)} nodes, {len(edges)} edges")

    return DiseaseNetworkExportResponse(
        nodes=nodes,
        edges=edges,
        query_params=query_params
    )


# ============================================================================
# 5. Regulations Export (Phase 9.3: 前端 xlsx 迁移到后端)
# ============================================================================

@router.get(
    "/regulations",
    response_model=RegulationsExportResponse,
    responses={
        200: {
            "description": "成功导出数据",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/RegulationsExportResponse"}},
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                },
            },
        },
    },
)
@rate_limit("5/minute")
def export_regulations(
    request: Request,
    min_ba: Optional[float] = Query(None, ge=0, description="最小结合亲和力 (BA)"),
    max_ba: Optional[float] = Query(None, ge=0, description="最大结合亲和力 (BA)"),
    species_ids: Optional[str] = Query(None, max_length=50, description="物种 ID 列表（逗号分隔，如 '1,2,3'）"),
    chromosomes: Optional[str] = Query(None, max_length=500, description="染色体列表（逗号分隔，如 'chr1,chr2'）"),
    lncrna_gene_name: Optional[str] = Query(None, max_length=100, description="lncRNA 基因名（模糊搜索）"),
    target_gene_name: Optional[str] = Query(None, max_length=100, description="靶基因名（模糊搜索）"),
    limit: int = Query(10000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    output_format: Literal["json", "csv", "excel", "jsonl"] = Query("json", alias="format", description="导出格式 (json/csv/excel/jsonl)"),
    db: Session = Depends(get_db),
):
    """
    导出调控关系数据（替代前端 xlsx 库）

    **应用场景**:
    - 前端 Regulations 页面的批量导出功能
    - 支持 CSV 和 Excel 格式下载
    - 与前端筛选参数完全兼容

    **筛选参数**:
    - min_ba/max_ba: 结合亲和力范围
    - species_ids: 物种 ID（逗号分隔，如 "1,2"）
    - chromosomes: 染色体（逗号分隔，如 "chr1,chr2"）
    - lncrna_gene_name: lncRNA 名称（模糊搜索）
    - target_gene_name: 靶基因名称（模糊搜索）

    **返回字段**:
    - regulation_id: 调控关系 ID
    - lncrna_gene_name: lncRNA 名称
    - target_gene_name: 靶基因名称
    - species_name: 物种名称
    - target_chromosome: 染色体
    - target_start/end: 位置
    - binding_affinity: BA 值
    - num_peaks: 峰数量

    **性能**: 10000 条记录 < 5s
    **内存优化**:
    - JSON 模式: 全量加载进内存，限制 5000 条（大数据集请使用 jsonl 格式）
    - CSV/JSONL: 真流式 O(1)
    - Excel: write_only 模式降低内存峰值
    """
    logger.info(
        "[EXPORT] regulations: min_ba=%s, max_ba=%s, species_ids=%s, chromosomes=%s, lncrna=%s, target=%s, limit=%s, output_format=%s",
        min_ba,
        max_ba,
        sanitize_for_log(species_ids, max_length=200),
        sanitize_for_log(chromosomes, max_length=500),
        sanitize_for_log(lncrna_gene_name, max_length=200),
        sanitize_for_log(target_gene_name, max_length=200),
        limit,
        output_format,
    )

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    # JSON 模式独立限制（防止内存峰值）；默认 limit 过大时自动降级到 MAX_JSON_LIMIT
    limit = _apply_json_memory_limit(request, limit, output_format)

    # Phase 9.17: 使用共享验证器解析逗号分隔参数（统一项数/长度限制，防止 DoS）
    species_id_list = parse_int_list(species_ids, param_name="species_ids", min_value=1, max_value=4)
    chromosome_list = parse_comma_list(chromosomes, param_name="chromosomes")

    stmt = build_regulations_export_stmt(
        min_ba=min_ba,
        max_ba=max_ba,
        species_id_list=species_id_list,
        chromosome_list=chromosome_list,
        lncrna_gene_name=lncrna_gene_name,
        target_gene_name=target_gene_name,
        limit=limit,
    )

    # 定义列名（用于流式导出）
    fieldnames = [
        "regulation_id", "lncrna_gene_name", "target_gene_name", "species_name",
        "target_chromosome", "target_start", "target_end", "binding_affinity", "num_peaks"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = _execute_streaming(db, stmt)
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            output_format,
            "regulations_export",
        )

    # JSON: 标准响应
    result = db.execute(stmt)
    data = [dict(row._mapping) for row in result]

    query_params = {
        "min_ba": min_ba,
        "max_ba": max_ba,
        "species_ids": species_ids,
        "chromosomes": chromosomes,
        "lncrna_gene_name": lncrna_gene_name,
        "target_gene_name": target_gene_name,
        "limit": limit,
        "format": output_format
    }

    return RegulationsExportResponse(
        data=data,
        total=len(data),
        query_params=query_params
    )
