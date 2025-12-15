"""
可视化数据 API 路由

提供高级可视化（Sankey Flow Diagram）的数据接口
"""
import logging
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.schemas.visualization import (
    SankeyResponse,
    SankeyData,
    SankeyNode,
    SankeyLink,
    SankeyStats,
    ChordResponse,
    ChordData,
    ChordNode,
    ChordLink,
    ChordStats,
)
from app.core.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/sankey-data", response_model=SankeyResponse)
def get_sankey_data(
    species_id: int = Query(default=1, ge=1, le=4, description="物种 ID (1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴)"),
    min_ba: float = Query(default=100.0, ge=0, description="最小结合亲和力阈值"),
    trait_name: Optional[str] = Query(default=None, description="疾病/性状名称筛选（模糊搜索）"),
    limit: int = Query(default=500, ge=1, le=5000, description="最大返回数据量"),
    db: Session = Depends(get_db),
):
    """
    获取 Sankey 流向图数据（三层：lncRNA -> Gene -> Disease）

    **应用场景**:
    - 可视化 lncRNA -> 靶基因 -> 疾病的三层调控网络
    - 识别关键调控通路和疾病关联
    - 研究 lncRNA 在疾病中的调控作用

    **数据结构**:
    ```
    lncRNA (layer 0) --[regulation]--> Gene (layer 1) --[association]--> Disease (layer 2)
    ```

    **节点类型**:
    - layer 0: lncRNA 基因
    - layer 1: 靶基因（蛋白编码基因）
    - layer 2: 疾病/性状

    **连接权重**:
    - lncRNA->Gene: 平均结合亲和力 (BA)
    - Gene->Disease: -log10(p-value)，p-value 越小权重越大

    **查询参数说明**:
    - species_id: 物种筛选，默认人类 (1)
    - min_ba: 最小结合亲和力，筛选强调控关系，默认 100
    - trait_name: 疾病名称模糊搜索，如 "diabetes", "cancer"
    - limit: 限制返回数据量，避免前端渲染压力

    **性能**: 500 条数据 < 100ms

    **示例请求**:
    ```bash
    # 获取人类 diabetes 相关的 Sankey 数据
    GET /api/v1/visualization/sankey-data?species_id=1&min_ba=100&trait_name=diabetes&limit=500
    ```

    **返回格式**:
    ```json
    {
      "success": true,
      "data": {
        "nodes": [
          {"id": "lncrna_123", "name": "MALAT1", "layer": 0},
          {"id": "gene_456", "name": "TP53", "layer": 1},
          {"id": "disease_789", "name": "Type 2 Diabetes", "layer": 2}
        ],
        "links": [
          {"source": "lncrna_123", "target": "gene_456", "value": 150.5, "flow_count": 12},
          {"source": "gene_456", "target": "disease_789", "value": 1e-8, "flow_count": 5}
        ]
      },
      "stats": {
        "total_lncrnas": 45,
        "total_genes": 120,
        "total_diseases": 10,
        "total_regulations": 180,
        "total_associations": 150,
        "avg_binding_affinity": 125.3,
        "species_id": 1
      }
    }
    ```
    """
    logger.info(
        f"[SANKEY] species_id={species_id}, min_ba={min_ba}, "
        f"trait_name={trait_name}, limit={limit}"
    )

    # ========================================================================
    # Step 1: 查询三层数据（使用聚合去重）
    # ========================================================================
    # 使用 GROUP BY 聚合，避免重复连接
    # 同时计算平均 BA 和流经记录数
    sql = text("""
        WITH regulation_agg AS (
            -- 聚合 lncRNA -> Gene 调控关系（去重 + 计算平均 BA）
            SELECT
                r.lncrna_gene_id,
                lnc.gene_name as lncrna_name,
                r.target_gene_id,
                tgt.gene_name as target_gene_name,
                tgt.core_id as target_core_id,
                AVG(r.binding_affinity) as avg_ba,
                COUNT(*) as regulation_count
            FROM regulations r
            JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
            JOIN genes tgt ON r.target_gene_id = tgt.gene_id
            WHERE r.species_id = :species_id
              AND r.binding_affinity >= :min_ba
              AND tgt.core_id IS NOT NULL  -- 必须有 core_id 才能关联疾病
            GROUP BY r.lncrna_gene_id, lnc.gene_name, r.target_gene_id, tgt.gene_name, tgt.core_id
        ),
        disease_agg AS (
            -- 聚合 Gene -> Disease 关联（去重）
            SELECT
                tga.core_id,
                t.trait_id,
                t.trait_name,
                AVG(tga.trait_snp_pvalue) as avg_pvalue,
                COUNT(*) as association_count
            FROM trait_gene_associations tga
            JOIN traits t ON tga.trait_id = t.trait_id
            WHERE (:trait_name IS NULL OR t.trait_name ILIKE '%' || :trait_name || '%')
            GROUP BY tga.core_id, t.trait_id, t.trait_name
        )
        -- 连接两层数据
        SELECT
            ra.lncrna_gene_id,
            ra.lncrna_name,
            ra.target_gene_id,
            ra.target_gene_name,
            ra.target_core_id,
            ra.avg_ba,
            ra.regulation_count,
            da.trait_id,
            da.trait_name,
            da.avg_pvalue,
            da.association_count
        FROM regulation_agg ra
        JOIN disease_agg da ON ra.target_core_id = da.core_id
        ORDER BY ra.avg_ba DESC, da.avg_pvalue ASC
        LIMIT :limit
    """)

    result = db.execute(
        sql,
        {
            "species_id": species_id,
            "min_ba": min_ba,
            "trait_name": trait_name,
            "limit": limit,
        },
    )

    # ========================================================================
    # Step 2: 构建 Sankey 节点和连接
    # ========================================================================
    nodes_dict = {}  # {node_id: SankeyNode}
    links = []
    seen_links = set()  # Track (source, target) pairs for O(1) deduplication

    # 统计信息
    lncrna_ids = set()
    gene_ids = set()
    disease_ids = set()
    total_regulations = 0
    total_associations = 0
    ba_values = []

    for row in result:
        lncrna_gene_id = row.lncrna_gene_id
        lncrna_name = row.lncrna_name
        target_gene_id = row.target_gene_id
        target_gene_name = row.target_gene_name
        avg_ba = float(row.avg_ba) if row.avg_ba else 0
        regulation_count = row.regulation_count
        trait_id = row.trait_id
        trait_name = row.trait_name
        avg_pvalue = float(row.avg_pvalue) if row.avg_pvalue else None
        association_count = row.association_count

        # 节点 ID
        lncrna_node_id = f"lncrna_{lncrna_gene_id}"
        gene_node_id = f"gene_{target_gene_id}"
        disease_node_id = f"disease_{trait_id}"

        # 添加 lncRNA 节点（layer 0）
        if lncrna_node_id not in nodes_dict:
            nodes_dict[lncrna_node_id] = SankeyNode(
                id=lncrna_node_id, name=lncrna_name, layer=0
            )
            lncrna_ids.add(lncrna_gene_id)

        # 添加基因节点（layer 1）
        if gene_node_id not in nodes_dict:
            nodes_dict[gene_node_id] = SankeyNode(
                id=gene_node_id, name=target_gene_name, layer=1
            )
            gene_ids.add(target_gene_id)

        # 添加疾病节点（layer 2）
        if disease_node_id not in nodes_dict:
            nodes_dict[disease_node_id] = SankeyNode(
                id=disease_node_id, name=trait_name, layer=2
            )
            disease_ids.add(trait_id)

        # 添加 lncRNA -> Gene 连接
        # 使用集合进行 O(1) 去重（避免同一对 lncRNA-Gene 多次出现）
        link_key_1 = (lncrna_node_id, gene_node_id)
        if link_key_1 not in seen_links:
            seen_links.add(link_key_1)
            links.append(
                SankeyLink(
                    source=lncrna_node_id,
                    target=gene_node_id,
                    value=avg_ba,
                    flow_count=regulation_count,
                )
            )
            total_regulations += regulation_count
            ba_values.append(avg_ba)

        # 添加 Gene -> Disease 连接
        link_key_2 = (gene_node_id, disease_node_id)
        if link_key_2 not in seen_links:
            seen_links.add(link_key_2)
            # 使用 -log10(p-value) 作为权重，如果 p-value 缺失则使用 1.0
            # 这样权重始终为正，且更小的 p-value (更显著) 得到更高的权重
            try:
                pvalue_weight = -math.log10(avg_pvalue) if avg_pvalue and avg_pvalue > 0 else 1.0
            except (ValueError, TypeError):
                pvalue_weight = 1.0

            links.append(
                SankeyLink(
                    source=gene_node_id,
                    target=disease_node_id,
                    value=pvalue_weight,
                    flow_count=association_count,
                )
            )
            total_associations += association_count

    # ========================================================================
    # Step 3: 构建响应
    # ========================================================================
    nodes = list(nodes_dict.values())

    # 计算平均结合亲和力
    avg_ba = sum(ba_values) / len(ba_values) if ba_values else 0

    stats = SankeyStats(
        total_lncrnas=len(lncrna_ids),
        total_genes=len(gene_ids),
        total_diseases=len(disease_ids),
        total_regulations=total_regulations,
        total_associations=total_associations,
        avg_binding_affinity=avg_ba,
        species_id=species_id,
    )

    query_params = {
        "species_id": species_id,
        "min_ba": min_ba,
        "trait_name": trait_name,
        "limit": limit,
    }

    logger.info(
        f"[SANKEY] Generated {len(nodes)} nodes, {len(links)} links "
        f"(lncRNA: {stats.total_lncrnas}, Gene: {stats.total_genes}, "
        f"Disease: {stats.total_diseases})"
    )

    return SankeyResponse(
        success=True,
        data=SankeyData(nodes=nodes, links=links),
        stats=stats,
        query_params=query_params,
    )


@router.get("/chord-data", response_model=ChordResponse)
def get_chord_data(
    species_id: int = Query(default=1, ge=1, le=4, description="物种 ID (1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴)"),
    lncrna_id: Optional[int] = Query(default=None, description="指定 lncRNA 基因 ID（可选）"),
    min_ba: float = Query(default=50.0, ge=0, description="最小结合亲和力阈值"),
    limit: int = Query(default=100, ge=1, le=500, description="最大返回节点数量"),
    db: Session = Depends(get_db),
):
    """
    获取 Chord 图数据（lncRNA-Gene 调控网络）

    **应用场景**:
    - 可视化 lncRNA 与其靶基因之间的调控关系网络
    - 展示双向调控关系（使用 Chord 图的环形布局）
    - 分析特定 lncRNA 的靶基因网络或高亲和力调控网络

    **数据结构**:
    - 节点：lncRNA 和 Gene（蛋白编码基因）
    - 连接：调控关系，权重为结合亲和力 (BA)
    - 矩阵：n×n 邻接矩阵，用于标准 D3 Chord 图渲染

    **两种查询模式**:

    1. **指定 lncRNA 模式** (`lncrna_id` 参数存在):
       - 返回该 lncRNA 与其所有靶基因的调控关系
       - 适用于研究特定 lncRNA 的功能
       - 示例: `/chord-data?species_id=1&lncrna_id=123&min_ba=50`

    2. **全局高亲和力模式** (`lncrna_id` 参数为空):
       - 返回高亲和力的 lncRNA-Gene 调控网络
       - 按 BA 值降序排序，返回 Top N 调控关系
       - 适用于发现关键调控通路
       - 示例: `/chord-data?species_id=1&min_ba=100&limit=100`

    **查询参数说明**:
    - species_id: 物种筛选，默认人类 (1)
    - lncrna_id: 可选，指定 lncRNA 基因 ID
    - min_ba: 最小结合亲和力，筛选强调控关系，默认 50
    - limit: 限制返回节点数，避免前端渲染压力，默认 100，最大 500

    **邻接矩阵说明**:
    - matrix[i][j] 表示节点 i 到节点 j 的权重（BA 值）
    - 矩阵是方阵，节点顺序与 nodes 列表一致
    - 用于标准 D3.js Chord 图渲染

    **性能**: 100 节点 < 200ms（含缓存）

    **示例请求**:
    ```bash
    # 查询特定 lncRNA 的靶基因网络
    GET /api/v1/visualization/chord-data?species_id=1&lncrna_id=123&min_ba=50&limit=100

    # 查询全局高亲和力网络（Top 100）
    GET /api/v1/visualization/chord-data?species_id=1&min_ba=150&limit=100
    ```

    **返回格式**:
    ```json
    {
      "success": true,
      "data": {
        "nodes": [
          {"id": "lncrna_123", "name": "MALAT1", "category": "lncrna", "value": 150.5},
          {"id": "gene_456", "name": "TP53", "category": "gene", "value": 125.3}
        ],
        "links": [
          {"source": "lncrna_123", "target": "gene_456", "value": 150.5}
        ],
        "matrix": [
          [0, 150.5],
          [0, 0]
        ]
      },
      "stats": {
        "total_nodes": 50,
        "total_lncrnas": 10,
        "total_genes": 40,
        "total_links": 120,
        "avg_binding_affinity": 125.3,
        "max_binding_affinity": 200.0,
        "min_binding_affinity": 50.0,
        "species_id": 1
      }
    }
    ```
    """
    logger.info(
        f"[CHORD] species_id={species_id}, lncrna_id={lncrna_id}, "
        f"min_ba={min_ba}, limit={limit}"
    )

    # ========================================================================
    # Step 1: 生成缓存键并尝试从缓存获取
    # ========================================================================
    cache_key = cache.make_list_key(
        "visualization:chord",
        species_id=species_id,
        lncrna_id=lncrna_id or "all",
        min_ba=min_ba,
        limit=limit,
    )

    # 尝试从缓存读取
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"[CHORD] Cache HIT: {cache_key}")
        return ChordResponse(**cached)

    # ========================================================================
    # Step 2: 构建 SQL 查询（根据是否指定 lncRNA ID）
    # ========================================================================
    if lncrna_id is not None:
        # 模式 1: 查询指定 lncRNA 的所有靶基因
        sql = text("""
            SELECT
                r.lncrna_gene_id,
                lnc.gene_name as lncrna_name,
                r.target_gene_id,
                tgt.gene_name as target_name,
                AVG(r.binding_affinity) as avg_ba,
                COUNT(*) as regulation_count
            FROM regulations r
            JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
            JOIN genes tgt ON r.target_gene_id = tgt.gene_id
            WHERE r.species_id = :species_id
              AND r.lncrna_gene_id = :lncrna_id
              AND r.binding_affinity >= :min_ba
            GROUP BY r.lncrna_gene_id, lnc.gene_name, r.target_gene_id, tgt.gene_name
            ORDER BY avg_ba DESC
            LIMIT :limit
        """)
        params = {
            "species_id": species_id,
            "lncrna_id": lncrna_id,
            "min_ba": min_ba,
            "limit": limit,
        }
    else:
        # 模式 2: 查询全局高亲和力调控关系
        sql = text("""
            SELECT
                r.lncrna_gene_id,
                lnc.gene_name as lncrna_name,
                r.target_gene_id,
                tgt.gene_name as target_name,
                AVG(r.binding_affinity) as avg_ba,
                COUNT(*) as regulation_count
            FROM regulations r
            JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
            JOIN genes tgt ON r.target_gene_id = tgt.gene_id
            WHERE r.species_id = :species_id
              AND r.binding_affinity >= :min_ba
            GROUP BY r.lncrna_gene_id, lnc.gene_name, r.target_gene_id, tgt.gene_name
            ORDER BY avg_ba DESC
            LIMIT :limit
        """)
        params = {
            "species_id": species_id,
            "min_ba": min_ba,
            "limit": limit,
        }

    result = db.execute(sql, params)

    # ========================================================================
    # Step 3: 构建节点和连接
    # ========================================================================
    nodes_dict = {}  # {node_id: ChordNode}
    links = []
    node_weights = {}  # {node_id: total_weight} 用于计算节点大小
    ba_values = []

    for row in result:
        lncrna_gene_id = row.lncrna_gene_id
        lncrna_name = row.lncrna_name
        target_gene_id = row.target_gene_id
        target_name = row.target_name
        avg_ba = float(row.avg_ba) if row.avg_ba else 0
        regulation_count = row.regulation_count

        # 节点 ID
        lncrna_node_id = f"lncrna_{lncrna_gene_id}"
        gene_node_id = f"gene_{target_gene_id}"

        # 累加节点权重（所有相关调控关系的 BA 总和）
        node_weights[lncrna_node_id] = node_weights.get(lncrna_node_id, 0) + avg_ba
        node_weights[gene_node_id] = node_weights.get(gene_node_id, 0) + avg_ba

        # 添加 lncRNA 节点
        if lncrna_node_id not in nodes_dict:
            nodes_dict[lncrna_node_id] = {
                "id": lncrna_node_id,
                "name": lncrna_name,
                "category": "lncrna",
                "value": 0,  # 稍后更新
            }

        # 添加基因节点
        if gene_node_id not in nodes_dict:
            nodes_dict[gene_node_id] = {
                "id": gene_node_id,
                "name": target_name,
                "category": "gene",
                "value": 0,  # 稍后更新
            }

        # 添加连接
        links.append(
            ChordLink(
                source=lncrna_node_id,
                target=gene_node_id,
                value=avg_ba,
            )
        )

        ba_values.append(avg_ba)

    # 更新节点权重
    for node_id, weight in node_weights.items():
        if node_id in nodes_dict:
            nodes_dict[node_id]["value"] = weight

    # 转换为 ChordNode 列表
    nodes = [ChordNode(**node_data) for node_data in nodes_dict.values()]

    # ========================================================================
    # Step 4: 构建邻接矩阵（用于 D3 Chord 图）
    # ========================================================================
    # 创建节点索引映射
    node_index = {node.id: i for i, node in enumerate(nodes)}
    n = len(nodes)

    # 初始化 n×n 矩阵
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]

    # 填充矩阵
    for link in links:
        source_idx = node_index.get(link.source)
        target_idx = node_index.get(link.target)
        if source_idx is not None and target_idx is not None:
            matrix[source_idx][target_idx] = link.value

    # ========================================================================
    # Step 5: 计算统计信息
    # ========================================================================
    lncrna_count = sum(1 for node in nodes if node.category == "lncrna")
    gene_count = sum(1 for node in nodes if node.category == "gene")

    avg_ba = sum(ba_values) / len(ba_values) if ba_values else 0
    max_ba = max(ba_values) if ba_values else 0
    min_ba_val = min(ba_values) if ba_values else 0

    stats = ChordStats(
        total_nodes=len(nodes),
        total_lncrnas=lncrna_count,
        total_genes=gene_count,
        total_links=len(links),
        avg_binding_affinity=avg_ba,
        max_binding_affinity=max_ba,
        min_binding_affinity=min_ba_val,
        species_id=species_id,
    )

    query_params = {
        "species_id": species_id,
        "lncrna_id": lncrna_id,
        "min_ba": min_ba,
        "limit": limit,
    }

    # ========================================================================
    # Step 6: 构建响应并缓存
    # ========================================================================
    response_data = {
        "success": True,
        "data": {
            "nodes": [node.model_dump() for node in nodes],
            "links": [link.model_dump() for link in links],
            "matrix": matrix,
        },
        "stats": stats.model_dump(),
        "query_params": query_params,
    }

    # 缓存 10 分钟
    cache.set(cache_key, response_data, ttl=cache.TTL_DETAIL)

    logger.info(
        f"[CHORD] Generated {len(nodes)} nodes, {len(links)} links "
        f"(lncRNA: {lncrna_count}, Gene: {gene_count})"
    )

    return ChordResponse(
        success=True,
        data=ChordData(nodes=nodes, links=links, matrix=matrix),
        stats=stats,
        query_params=query_params,
    )
