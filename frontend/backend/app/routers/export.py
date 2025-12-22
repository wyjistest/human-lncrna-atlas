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
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.utils import escape_like_pattern
from app.core.validators import parse_int_list, parse_comma_list
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
MAX_JSON_LIMIT = 5000     # JSON 模式全量加载进内存，限制为 5000 条


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


# ============================================================================
# 1. High-Affinity Export
# ============================================================================

@router.get("/high-affinity", response_model=HighAffinityExportResponse)
@rate_limit("5/minute")
def export_high_affinity(
    request: Request,
    min_ba: float = Query(100.0, ge=0, description="最小结合亲和力 (BA)"),
    species_id: Optional[int] = Query(None, description="物种 ID 筛选 (1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴)"),
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
    logger.info(f"[EXPORT] high-affinity: min_ba={min_ba}, species_id={species_id}, limit={limit}, output_format={output_format}")

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    # 构建 SQL 查询
    sql = text("""
        SELECT
            r.lncrna_gene_id,
            lnc.gene_name as lncrna_name,
            r.target_gene_id,
            tgt.gene_name as target_name,
            r.binding_affinity,
            r.species_id,
            s.display_name as species_name,
            r.target_chromosome as chr,
            r.target_start as start_in_genome,
            r.target_end as end_in_genome
        FROM regulations r
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        JOIN genes tgt ON r.target_gene_id = tgt.gene_id
        JOIN species s ON r.species_id = s.species_id
        WHERE r.binding_affinity >= :min_ba
          AND (:species_id IS NULL OR r.species_id = :species_id)
        ORDER BY r.binding_affinity DESC
        LIMIT :limit
    """)

    # 定义列名（用于流式导出）
    fieldnames = [
        "lncrna_gene_id", "lncrna_name", "target_gene_id", "target_name",
        "binding_affinity", "species_id", "species_name", "chr",
        "start_in_genome", "end_in_genome"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = db.execute(sql, {
            "min_ba": min_ba,
            "species_id": species_id,
            "limit": limit
        })
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            output_format,
            "high_affinity_regulations",
        )

    # JSON: 标准响应（需要 total 字段）
    result = db.execute(sql, {
        "min_ba": min_ba,
        "species_id": species_id,
        "limit": limit
    })
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
    logger.info(f"[EXPORT] conservation: min_species_count={min_species_count}, limit={limit}, output_format={output_format}")

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

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
        result = db.execute(sql, {
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
    logger.info(f"[EXPORT] chipseq-overlaps: mark_names={mark_names}, min_ba={min_ba}, limit={limit}, output_format={output_format}")

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    if not mark_names:
        raise HTTPException(
            status_code=400,
            detail="At least one mark_name is required"
        )

    # 使用物化视图查询（性能优化）
    sql = text("""
        SELECT
            o.regulation_id,
            lnc.gene_name as lncrna_name,
            tgt.gene_name as target_name,
            r.binding_affinity,
            mt.mark_name,
            o.fold_enrichment as peak_score,
            o.chromosome as peak_chr,
            o.peak_start,
            o.peak_end,
            o.cell_type
        FROM mv_lncrna_chipseq_overlaps o
        JOIN regulations r ON o.regulation_id = r.regulation_id
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        JOIN genes tgt ON r.target_gene_id = tgt.gene_id
        JOIN epigenetic_mark_types mt ON o.mark_type_id = mt.mark_type_id
        WHERE mt.mark_name = ANY(:mark_names)
          AND r.binding_affinity >= :min_ba
        ORDER BY r.binding_affinity DESC, o.fold_enrichment DESC
        LIMIT :limit
    """)

    # 定义列名
    fieldnames = [
        "regulation_id", "lncrna_name", "target_name", "binding_affinity",
        "mark_name", "peak_score", "peak_chr", "peak_start", "peak_end", "cell_type"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = db.execute(sql, {
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
    import json
    import requests
    data = requests.get("http://localhost:8000/api/v1/export/disease-network?trait_name=diabetes").json()
    # 使用 py4cytoscape 导入
    ```

    **性能**: 5000 条边 < 5s
    """
    logger.info(f"[EXPORT] disease-network: trait_name={trait_name}, limit={limit}, output_format={output_format}")

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
            f"[EXPORT] disease-network: No effective trait_name filter provided "
            f"(value={trait_name!r}), limiting to {effective_limit} rows (requested: {limit})"
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
    disease_gene_sql = text("""
        SELECT
            t.trait_name,
            t.trait_id,
            g.gene_id,
            g.gene_name,
            tga.trait_snp_pvalue as pvalue
        FROM trait_gene_associations tga
        JOIN traits t ON tga.trait_id = t.trait_id
        JOIN genes g ON tga.core_id = g.core_id
        WHERE (:trait_name IS NULL OR t.trait_name ILIKE '%' || :trait_name || '%' ESCAPE '\\')
        LIMIT :limit
    """)

    disease_gene_result = db.execute(disease_gene_sql, {
        "trait_name": escaped_trait_name,
        "limit": effective_limit
    })

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
        f"[EXPORT] regulations: min_ba={min_ba}, max_ba={max_ba}, "
        f"species_ids={species_ids}, chromosomes={chromosomes}, "
        f"lncrna={lncrna_gene_name}, target={target_gene_name}, "
        f"limit={limit}, output_format={output_format}"
    )

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    # JSON 模式独立限制（防止内存峰值）
    if output_format == "json" and limit > MAX_JSON_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"JSON format is limited to {MAX_JSON_LIMIT} records due to memory constraints. "
                f"For larger datasets, please use 'jsonl' (JSON Lines) format which supports up to {MAX_EXPORT_LIMIT} records."
            )
        )

    # Phase 9.17: 使用共享验证器解析逗号分隔参数（统一项数/长度限制，防止 DoS）
    species_id_list = parse_int_list(species_ids, param_name="species_ids")
    chromosome_list = parse_comma_list(chromosomes, param_name="chromosomes")

    # 构建动态 SQL（使用参数化查询防止 SQL 注入）
    conditions = []
    params = {"limit": limit}

    # Phase 9.16: 移除 CAST，直接比较 DECIMAL 类型，允许 PostgreSQL 使用索引
    # 参考: Codex 代码审查 - CAST(... AS FLOAT) 会阻止索引使用
    if min_ba is not None:
        conditions.append("r.binding_affinity >= :min_ba")
        params["min_ba"] = min_ba

    if max_ba is not None:
        conditions.append("r.binding_affinity <= :max_ba")
        params["max_ba"] = max_ba

    if species_id_list:
        conditions.append("r.species_id = ANY(:species_ids)")
        params["species_ids"] = species_id_list

    if chromosome_list:
        conditions.append("r.target_chromosome = ANY(:chromosomes)")
        params["chromosomes"] = chromosome_list

    # Phase 9.17: LIKE 模式转义，防止通配符绕过导致全表扫描 DoS
    # 同时检查 .strip() 避免纯空白字符串被当作有效过滤条件
    if lncrna_gene_name and lncrna_gene_name.strip():
        conditions.append("lnc.gene_name ILIKE '%' || :lncrna_name || '%' ESCAPE '\\'")
        params["lncrna_name"] = escape_like_pattern(lncrna_gene_name.strip())

    if target_gene_name and target_gene_name.strip():
        conditions.append("tgt.gene_name ILIKE '%' || :target_name || '%' ESCAPE '\\'")
        params["target_name"] = escape_like_pattern(target_gene_name.strip())

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = text(f"""
        SELECT
            r.regulation_id,
            lnc.gene_name as lncrna_gene_name,
            tgt.gene_name as target_gene_name,
            s.display_name as species_name,
            r.target_chromosome,
            r.target_start,
            r.target_end,
            CAST(r.binding_affinity AS FLOAT) as binding_affinity,
            r.num_peaks
        FROM regulations r
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        JOIN genes tgt ON r.target_gene_id = tgt.gene_id
        JOIN species s ON r.species_id = s.species_id
        WHERE {where_clause}
        ORDER BY r.binding_affinity DESC NULLS LAST
        LIMIT :limit
    """)

    # 定义列名（用于流式导出）
    fieldnames = [
        "regulation_id", "lncrna_gene_name", "target_gene_name", "species_name",
        "target_chromosome", "target_start", "target_end", "binding_affinity", "num_peaks"
    ]

    # CSV/Excel: 使用流式输出
    if output_format in ("csv", "excel", "jsonl"):
        result = db.execute(sql, params)
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            output_format,
            "regulations_export",
        )

    # JSON: 标准响应
    result = db.execute(sql, params)
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
