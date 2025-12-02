"""网络分析API路由"""
from collections import Counter
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_

from app.core.database import get_db
from app.models import Regulation, Gene, CoreGene, TraitGeneAssociation, Trait, Ontology, Species
from app.schemas.regulation import NetworkData, NetworkNode, NetworkEdge

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/available-combinations")
def get_available_combinations(
    species_id: Optional[int] = Query(None, description="物种ID过滤"),
    db: Session = Depends(get_db),
):
    """
    获取有网络数据的疾病-Ontology组合列表
    """
    query = (
        db.query(
            TraitGeneAssociation.trait_id,
            TraitGeneAssociation.ontology_id,
            TraitGeneAssociation.evidence_species_id,
        )
        .join(CoreGene, TraitGeneAssociation.core_id == CoreGene.core_id)
        .filter(CoreGene.gene_type == "lncRNA")
    )

    if species_id:
        query = query.filter(TraitGeneAssociation.evidence_species_id == species_id)

    combinations = query.distinct().all()

    return {
        "combinations": [
            {
                "trait_id": c.trait_id,
                "ontology_id": c.ontology_id,
                "species_id": c.evidence_species_id,
            }
            for c in combinations
        ]
    }


@router.get("/disease", response_model=NetworkData)
def get_disease_network(
    trait_id: int = Query(..., description="Trait ID"),
    ontology_id: int = Query(..., description="Ontology ID"),
    species_id: Optional[int] = Query(None, description="物种ID过滤"),
    min_ba: Optional[float] = Query(50, ge=0, description="最小结合亲和力(默认50)"),
    max_nodes: int = Query(500, ge=1, le=2000, description="最大节点数"),
    max_edges: int = Query(2000, ge=1, le=10000, description="最大边数"),
    db: Session = Depends(get_db),
):
    """
    根据疾病-Ontology组合获取调控网络

    返回该组合下所有相关lncRNA及其调控的靶基因网络
    """
    # 验证trait和ontology存在
    trait = db.query(Trait).filter(Trait.trait_id == trait_id).first()
    ontology = db.query(Ontology).filter(Ontology.ontology_id == ontology_id).first()

    if not trait:
        raise HTTPException(status_code=404, detail="Trait not found")
    if not ontology:
        raise HTTPException(status_code=404, detail="Ontology not found")

    # 获取该trait-ontology组合下的所有关联基因的core_id（包括lncRNA和靶基因）
    associated_core_ids = (
        db.query(TraitGeneAssociation.core_id)
        .filter(TraitGeneAssociation.trait_id == trait_id)
        .filter(TraitGeneAssociation.ontology_id == ontology_id)
        .distinct()
    )

    associated_core_ids = [row[0] for row in associated_core_ids.all()]

    if not associated_core_ids:
        return NetworkData(nodes=[], edges=[], stats={})

    # 获取这些基因在指定物种的同源基因（限制数量避免内存溢出）
    genes_query = (
        db.query(Gene, CoreGene)
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .filter(Gene.core_id.in_(associated_core_ids))
    )

    if species_id:
        genes_query = genes_query.filter(Gene.species_id == species_id)

    # 限制节点数量
    genes_query = genes_query.limit(max_nodes)
    genes = genes_query.all()
    gene_ids = [gene.gene_id for gene, _ in genes]

    if not gene_ids:
        return NetworkData(nodes=[], edges=[], stats={})

    # 初始化节点和边
    nodes_dict = {}
    edges = []

    # 添加所有关联基因节点
    for gene, core_gene in genes:
        node_id = f"g_{gene.gene_id}"
        nodes_dict[node_id] = NetworkNode(
            id=node_id,
            label=gene.gene_name or gene.gene_ensembl_id,
            type=core_gene.gene_type,
            gene_id=gene.gene_id,
            core_id=gene.core_id,
        )

    # 获取这些基因之间的调控关系（lncRNA -> 靶基因，且两者都在关联基因列表中）
    regulations_query = (
        db.query(Regulation)
        .filter(Regulation.lncrna_gene_id.in_(gene_ids))
        .filter(Regulation.target_gene_id.in_(gene_ids))
    )

    if species_id:
        regulations_query = regulations_query.filter(Regulation.species_id == species_id)
    if min_ba is not None:
        regulations_query = regulations_query.filter(Regulation.binding_affinity >= min_ba)

    # 限制边的数量，按 BA 降序取最重要的边
    regulations_query = regulations_query.order_by(Regulation.binding_affinity.desc()).limit(max_edges)

    for reg in regulations_query.all():
        source_node_id = f"g_{reg.lncrna_gene_id}"
        target_node_id = f"g_{reg.target_gene_id}"

        # 添加边
        edges.append(
            NetworkEdge(
                source=source_node_id,
                target=target_node_id,
                binding_affinity=float(reg.binding_affinity) if reg.binding_affinity else None,
                regulation_id=reg.regulation_id,
            )
        )

    # 统计信息
    stats = {
        "total_nodes": len(nodes_dict),
        "total_edges": len(edges),
        "lncrna_count": sum(1 for n in nodes_dict.values() if n.type == "lncRNA"),
        "protein_coding_count": sum(1 for n in nodes_dict.values() if n.type == "protein_coding"),
        "trait_name": trait.trait_name,
        "ontology_name": ontology.ontology_name,
    }

    return NetworkData(nodes=list(nodes_dict.values()), edges=edges, stats=stats)


@router.get("/gene/{gene_id}/detail")
def get_gene_detail(
    gene_id: int,
    db: Session = Depends(get_db),
):
    """
    获取基因详细信息（用于节点点击详情）
    """
    # 查询基因信息
    gene_info = (
        db.query(Gene, CoreGene)
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .filter(Gene.gene_id == gene_id)
        .first()
    )

    if not gene_info:
        raise HTTPException(status_code=404, detail="Gene not found")

    gene, core_gene = gene_info

    # 合并多个统计查询为单次查询（优化：减少数据库往返）
    # 使用 CASE WHEN 同时统计作为源和作为目标的调控关系，以及总BA
    stats = (
        db.query(
            func.count(case((Regulation.lncrna_gene_id == gene_id, 1))).label("as_source_count"),
            func.count(case((Regulation.target_gene_id == gene_id, 1))).label("as_target_count"),
            func.sum(Regulation.binding_affinity).label("total_ba"),
        )
        .filter(or_(
            Regulation.lncrna_gene_id == gene_id,
            Regulation.target_gene_id == gene_id
        ))
        .first()
    )

    as_source_count = stats.as_source_count or 0
    as_target_count = stats.as_target_count or 0
    total_ba = stats.total_ba or 0

    # 获取物种信息（Species 已在文件顶部导入）
    species = db.query(Species).filter(Species.species_id == gene.species_id).first()

    # 计算保守性标签：统计该 core_id 在哪些物种中存在
    species_presence = (
        db.query(Gene.species_id)
        .filter(Gene.core_id == gene.core_id)
        .distinct()
        .order_by(Gene.species_id)
        .all()
    )

    # 生成保守性标签（4位二进制，1表示存在，0表示不存在）
    # 物种顺序：1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴
    conservation_label = ""
    for species_id in [1, 2, 3, 4]:
        if any(sp[0] == species_id for sp in species_presence):
            conservation_label += "1"
        else:
            conservation_label += "0"

    # 计算保守物种数量
    conservation_count = len(species_presence)

    return {
        "gene_id": gene.gene_id,
        "gene_name": gene.gene_name or gene.gene_ensembl_id,
        "gene_ensembl_id": gene.gene_ensembl_id,
        "gene_type": core_gene.gene_type,
        "species_id": gene.species_id,
        "species_name": species.display_name if species else None,
        "chromosome": gene.chromosome,
        "start": gene.gene_start,
        "end": gene.gene_end,
        "strand": gene.strand,
        "core_id": gene.core_id,
        "conservation_label": conservation_label,
        "conservation_count": conservation_count,
        "connections": {
            "as_source": as_source_count,
            "as_target": as_target_count,
            "total": as_source_count + as_target_count,
            "total_ba": float(total_ba) if total_ba else 0
        }
    }


@router.get("/gene/{gene_id}", response_model=NetworkData)
def get_gene_network(
    gene_id: int,
    species_id: Optional[int] = Query(None, description="限制物种"),
    min_ba: Optional[float] = Query(0, ge=0, description="最小结合亲和力"),
    max_distance: Optional[int] = Query(None, description="最大距离（bp）"),
    depth: int = Query(1, ge=1, le=2, description="网络深度（1或2层）"),
    max_edges: int = Query(500, ge=1, le=5000, description="最大边数（默认500）"),
    db: Session = Depends(get_db),
):
    """
    获取基因的调控网络数据（用于Cytoscape可视化）

    - gene_id: 中心基因ID
    - species_id: 限制物种（None表示所有物种）
    - min_ba: 最小结合亲和力
    - max_distance: 最大距离过滤
    - depth: 网络深度（1=直接调控，2=二度调控）
    - max_edges: 最大边数限制，避免高连接度基因返回过多数据
    """
    # 验证基因存在
    center_gene = (
        db.query(Gene, CoreGene)
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .filter(Gene.gene_id == gene_id)
        .first()
    )

    if not center_gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    gene_obj, core_gene = center_gene

    # 初始化节点和边
    nodes_dict = {}
    edges = []

    # 添加中心节点
    center_node_id = f"g_{gene_obj.gene_id}"
    nodes_dict[center_node_id] = NetworkNode(
        id=center_node_id,
        label=gene_obj.gene_name or gene_obj.gene_ensembl_id or f"Gene_{gene_obj.gene_id}",
        type=core_gene.gene_type,
        gene_id=gene_obj.gene_id,
        core_id=gene_obj.core_id,
    )

    # 第一层：获取直接调控关系（该基因作为lncRNA）
    query_1st = (
        db.query(Regulation, Gene, CoreGene)
        .join(Gene, Regulation.target_gene_id == Gene.gene_id)
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .filter(Regulation.lncrna_gene_id == gene_id)
    )

    if species_id:
        query_1st = query_1st.filter(Regulation.species_id == species_id)
    if min_ba is not None:
        query_1st = query_1st.filter(Regulation.binding_affinity >= min_ba)
    if max_distance is not None:
        query_1st = query_1st.filter(
            func.abs(Regulation.target_start - gene_obj.gene_start) <= max_distance
        )

    # 按 binding_affinity 降序排列，并限制边数（第一层使用大部分配额）
    first_layer_limit = max_edges if depth == 1 else int(max_edges * 0.7)
    query_1st = query_1st.order_by(Regulation.binding_affinity.desc()).limit(first_layer_limit)

    # 追踪是否数据被截断
    truncated = False

    for reg, target_gene, target_core in query_1st.all():
        # 添加目标节点
        target_node_id = f"g_{target_gene.gene_id}"
        if target_node_id not in nodes_dict:
            nodes_dict[target_node_id] = NetworkNode(
                id=target_node_id,
                label=target_gene.gene_name
                or target_gene.gene_ensembl_id
                or f"Gene_{target_gene.gene_id}",
                type=target_core.gene_type,
                gene_id=target_gene.gene_id,
                core_id=target_gene.core_id,
            )

        # 添加边
        edges.append(
            NetworkEdge(
                source=center_node_id,
                target=target_node_id,
                binding_affinity=float(reg.binding_affinity) if reg.binding_affinity else None,
                regulation_id=reg.regulation_id,
            )
        )

    # 第二层：如果depth=2，获取二度调控
    if depth >= 2:
        # 获取所有第一层目标基因的ID
        first_layer_gene_ids = [
            int(node.gene_id) for node_id, node in nodes_dict.items() if node_id != center_node_id
        ]

        if first_layer_gene_ids:
            query_2nd = (
                db.query(Regulation, Gene, CoreGene)
                .join(Gene, Regulation.target_gene_id == Gene.gene_id)
                .join(CoreGene, Gene.core_id == CoreGene.core_id)
                .filter(Regulation.lncrna_gene_id.in_(first_layer_gene_ids))
            )

            if species_id:
                query_2nd = query_2nd.filter(Regulation.species_id == species_id)
            if min_ba is not None:
                query_2nd = query_2nd.filter(Regulation.binding_affinity >= min_ba)

            # 限制第二层数量（使用剩余配额）
            second_layer_limit = max_edges - len(edges)
            if second_layer_limit <= 0:
                truncated = True
                second_layer_limit = 0
            query_2nd = query_2nd.order_by(Regulation.binding_affinity.desc()).limit(second_layer_limit)

            for reg, target_gene, target_core in query_2nd.all():
                source_node_id = f"g_{reg.lncrna_gene_id}"
                target_node_id = f"g_{target_gene.gene_id}"

                # 跳过指向中心节点的边（避免循环）
                if target_node_id == center_node_id:
                    continue

                # 添加目标节点
                if target_node_id not in nodes_dict:
                    nodes_dict[target_node_id] = NetworkNode(
                        id=target_node_id,
                        label=target_gene.gene_name
                        or target_gene.gene_ensembl_id
                        or f"Gene_{target_gene.gene_id}",
                        type=target_core.gene_type,
                        gene_id=target_gene.gene_id,
                        core_id=target_gene.core_id,
                    )

                # 添加边
                edges.append(
                    NetworkEdge(
                        source=source_node_id,
                        target=target_node_id,
                        binding_affinity=float(reg.binding_affinity)
                        if reg.binding_affinity
                        else None,
                        regulation_id=reg.regulation_id,
                    )
                )

    # 检查是否达到边数限制
    if len(edges) >= max_edges:
        truncated = True

    # 统计信息
    stats = {
        "total_nodes": len(nodes_dict),
        "total_edges": len(edges),
        "lncrna_count": sum(1 for n in nodes_dict.values() if n.type == "lncRNA"),
        "protein_coding_count": sum(1 for n in nodes_dict.values() if n.type == "protein_coding"),
        "avg_binding_affinity": (
            sum(e.binding_affinity for e in edges if e.binding_affinity is not None)
            / len([e for e in edges if e.binding_affinity is not None])
            if any(e.binding_affinity is not None for e in edges)
            else None
        ),
        "truncated": truncated,
        "max_edges_limit": max_edges,
    }

    return NetworkData(
        nodes=list(nodes_dict.values()),
        edges=edges,
        stats=stats,
    )


@router.get("/compare", response_model=dict)
def compare_species_networks(
    lncrna_gene_id: int = Query(..., description="lncRNA基因ID（human）"),
    min_ba: float = Query(50, ge=0, description="最小结合亲和力"),
    max_targets_per_species: int = Query(100, ge=1, le=500, description="每个物种最大靶基因数"),
    db: Session = Depends(get_db),
):
    """
    跨物种网络对比

    返回指定lncRNA在不同物种中的调控网络数据

    - lncrna_gene_id: lncRNA基因ID
    - min_ba: 最小结合亲和力过滤
    - max_targets_per_species: 每个物种返回的最大靶基因数，按 BA 降序取 TOP N
    """
    # 查询lncRNA的core_id
    lncrna = db.query(Gene).filter(Gene.gene_id == lncrna_gene_id).first()

    if not lncrna:
        raise HTTPException(status_code=404, detail="LncRNA not found")

    # 查询该core_id在所有物种的同源基因
    ortholog_genes = (
        db.query(Gene.gene_id, Gene.species_id)
        .filter(Gene.core_id == lncrna.core_id)
        .all()
    )

    # 对每个物种构建网络
    species_networks = {}

    for gene_id, species_id in ortholog_genes:
        # 查询该基因的调控关系（添加排序和限制）
        regulations_query = (
            db.query(Regulation, Gene, CoreGene)
            .join(Gene, Regulation.target_gene_id == Gene.gene_id)
            .join(CoreGene, Gene.core_id == CoreGene.core_id)
            .filter(Regulation.lncrna_gene_id == gene_id)
            .filter(Regulation.binding_affinity >= min_ba)
            .order_by(Regulation.binding_affinity.desc())
            .limit(max_targets_per_species)
        )

        regulations = regulations_query.all()

        # 查询该物种的总调控关系数（用于统计）
        total_count = (
            db.query(func.count(Regulation.regulation_id))
            .filter(Regulation.lncrna_gene_id == gene_id)
            .filter(Regulation.binding_affinity >= min_ba)
            .scalar()
        )

        targets = [
            {
                "target_gene_id": target_gene.gene_id,
                "target_name": target_gene.gene_name,
                "target_core_id": target_gene.core_id,
                "binding_affinity": float(reg.binding_affinity) if reg.binding_affinity else None,
            }
            for reg, target_gene, target_core in regulations
        ]

        species_networks[species_id] = {
            "lncrna_gene_id": gene_id,
            "species_id": species_id,
            "target_count": len(targets),
            "total_target_count": total_count,
            "truncated": total_count > max_targets_per_species,
            "targets": targets,
        }

    # 找到保守靶基因（在多个物种中共同存在的core_id）
    # Counter 已在文件顶部导入
    all_target_core_ids = []
    for network in species_networks.values():
        all_target_core_ids.extend([t["target_core_id"] for t in network["targets"]])

    core_id_counts = Counter(all_target_core_ids)
    conserved_targets = [core_id for core_id, count in core_id_counts.items() if count > 1]

    return {
        "lncrna_core_id": lncrna.core_id,
        "species_networks": species_networks,
        "conserved_target_count": len(conserved_targets),
        "conserved_targets": conserved_targets,
    }
