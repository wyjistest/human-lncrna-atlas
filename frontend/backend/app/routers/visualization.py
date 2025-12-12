"""
可视化数据 API 路由

提供高级可视化（Sankey Flow Diagram）的数据接口
"""
import logging
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.schemas.visualization import (
    SankeyResponse,
    SankeyData,
    SankeyNode,
    SankeyLink,
    SankeyStats,
)

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
        # 使用元组去重（避免同一对 lncRNA-Gene 多次出现）
        link_key_1 = (lncrna_node_id, gene_node_id)
        if not any(
            link.source == lncrna_node_id and link.target == gene_node_id
            for link in links
        ):
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
        if not any(
            link.source == gene_node_id and link.target == disease_node_id
            for link in links
        ):
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
