"""数据导出 API 路由

Phase 6.0-A: 为 Jupyter Notebook 数据分析提供便捷的数据导出 API

支持格式:
- JSON (默认)
- CSV (逗号分隔) - 真流式输出，内存占用 O(1)
- Excel (.xlsx) - write_only 模式，减少内存峰值

性能优化:
- 使用 LIMIT 限制返回数量（最大 50000）
- 真流式响应：逐行生成 CSV，不在内存中保存完整数据集
- 复用数据库连接池

Phase 9.3 改进：
- CR-005: 修复伪流式输出问题，改用生成器逐行 yield
"""
import logging
from typing import List, Optional, Dict, Any, Iterator, Generator
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.schemas.export import (
    HighAffinityExportResponse,
    ConservationExportResponse,
    ChipseqOverlapExportResponse,
    DiseaseNetworkExportResponse,
    NetworkNode,
    NetworkEdge,
)
from app.utils.streaming_export import (
    stream_csv_response,
    stream_excel_response,
    create_db_row_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])

# 最大导出数量限制（防止内存溢出）
MAX_EXPORT_LIMIT = 50000


def export_to_streaming_format(
    row_iterator: Iterator[Dict[str, Any]],
    fieldnames: List[str],
    format: str,
    filename: str,
    *,
    array_fields: Optional[List[str]] = None,
):
    """
    将数据导出为指定格式（真流式输出）

    Args:
        row_iterator: 数据行迭代器（生成器）
        fieldnames: 列名列表
        format: 导出格式 (csv/excel)
        filename: 文件名（不含扩展名）
        array_fields: 需要转换为逗号分隔字符串的数组字段

    Returns:
        StreamingResponse

    Note:
        JSON 格式不使用此函数，直接返回 Pydantic 响应模型
    """
    # 可选：转换数组字段为字符串
    def transform_arrays(row: Dict[str, Any]) -> Dict[str, Any]:
        if array_fields:
            for field in array_fields:
                if field in row and isinstance(row[field], (list, tuple)):
                    row[field] = ", ".join(str(v) for v in row[field] if v is not None)
        return row

    # 包装迭代器以应用转换
    def transformed_rows() -> Generator[Dict[str, Any], None, None]:
        for row in row_iterator:
            yield transform_arrays(row)

    if format == "csv":
        return stream_csv_response(
            transformed_rows(),
            fieldnames,
            f"{filename}.csv",
        )

    elif format == "excel":
        return stream_excel_response(
            transformed_rows(),
            fieldnames,
            f"{filename}.xlsx",
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


# ============================================================================
# 1. High-Affinity Export
# ============================================================================

@router.get("/high-affinity", response_model=HighAffinityExportResponse)
def export_high_affinity(
    min_ba: float = Query(100.0, ge=0, description="最小结合亲和力 (BA)"),
    species_id: Optional[int] = Query(None, description="物种 ID 筛选 (1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴)"),
    limit: int = Query(10000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    format: str = Query("json", description="导出格式 (json/csv/excel)"),
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
    **内存**: CSV/Excel 使用真流式输出，内存占用 O(1)
    """
    logger.info(f"[EXPORT] high-affinity: min_ba={min_ba}, species_id={species_id}, limit={limit}, format={format}")

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
    if format in ("csv", "excel"):
        result = db.execute(sql, {
            "min_ba": min_ba,
            "species_id": species_id,
            "limit": limit
        })
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            format,
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
        "format": format
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
def export_conservation(
    min_species_count: int = Query(2, ge=1, le=4, description="最少保守物种数"),
    limit: int = Query(5000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    format: str = Query("json", description="导出格式 (json/csv/excel)"),
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
    **内存**: CSV/Excel 使用真流式输出，内存占用 O(1)
    """
    logger.info(f"[EXPORT] conservation: min_species_count={min_species_count}, limit={limit}, format={format}")

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
    if format in ("csv", "excel"):
        result = db.execute(sql, {
            "min_species_count": min_species_count,
            "limit": limit
        })
        return export_to_streaming_format(
            create_db_row_generator(result, transform=transform_conservation_row),
            fieldnames,
            format,
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
        "format": format
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
def export_chipseq_overlaps(
    mark_names: List[str] = Query(
        default=["H3K4me3", "H3K27me3"],
        description="组蛋白标记列表（支持多个，如 H3K4me3, H3K27me3, H3K27ac）"
    ),
    min_ba: float = Query(100.0, ge=0, description="最小结合亲和力"),
    limit: int = Query(10000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回数量"),
    format: str = Query("json", description="导出格式 (json/csv/excel)"),
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
    **内存**: CSV/Excel 使用真流式输出，内存占用 O(1)
    """
    logger.info(f"[EXPORT] chipseq-overlaps: mark_names={mark_names}, min_ba={min_ba}, limit={limit}, format={format}")

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
    if format in ("csv", "excel"):
        result = db.execute(sql, {
            "mark_names": mark_names,
            "min_ba": min_ba,
            "limit": limit
        })
        return export_to_streaming_format(
            create_db_row_generator(result),
            fieldnames,
            format,
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
        "format": format
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
def export_disease_network(
    trait_name: Optional[str] = Query(
        None,
        description="疾病/性状名称（模糊搜索，如 'diabetes', 'cancer'）"
    ),
    limit: int = Query(5000, ge=1, le=MAX_EXPORT_LIMIT, description="最大返回边数"),
    format: str = Query("json", description="导出格式 (仅支持 json，网络数据不适合 CSV)"),
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
    logger.info(f"[EXPORT] disease-network: trait_name={trait_name}, limit={limit}, format={format}")

    # 验证参数
    if limit > MAX_EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit exceeds maximum allowed value ({MAX_EXPORT_LIMIT})"
        )

    if format != "json":
        raise HTTPException(
            status_code=400,
            detail="Disease network export only supports JSON format (network data structure)"
        )

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
        WHERE (:trait_name IS NULL OR t.trait_name ILIKE '%' || :trait_name || '%')
        LIMIT :limit
    """)

    disease_gene_result = db.execute(disease_gene_sql, {
        "trait_name": trait_name,
        "limit": limit
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
            "limit": limit
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
        "format": format
    }

    logger.info(f"[EXPORT] disease-network: {len(nodes)} nodes, {len(edges)} edges")

    return DiseaseNetworkExportResponse(
        nodes=nodes,
        edges=edges,
        query_params=query_params
    )
