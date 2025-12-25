"""
IGV.js 集成 API 路由
提供基因组浏览器配置和 BED 格式数据导出

主路由文件，包含配置端点并整合子路由
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.core.config import settings
from app.models import Species, Gene, Regulation, EpigeneticMarkType, ChIPSeqExperiment
from app.core.igv_utils import get_genome_reference, get_chipseq_mark_color
from app.config.igv_genomes import (
    GENOME_REFERENCES,
    GENE_ANNOTATION_TRACKS,
    CHIPSEQ_BIGBED_TRACKS,
    get_track_name_prefix,
)
from app.schemas.igv import (
    GenomeReference,
    IGVTrack,
    IGVConfig,
    IGVConfigResponse,
    SpeciesGenomeInfo,
    IGVSearchConfig,
)

# 导入子路由
from app.routers.igv_search import router as search_router
from app.routers.igv_regulations import router as regulations_router
from app.routers.igv_repeatmasker import router as repeatmasker_router
from app.routers.igv_chipseq import router as chipseq_router
from app.routers.igv_overlap_track import router as overlap_track_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/igv", tags=["igv"])

# 注册子路由
router.include_router(search_router)
router.include_router(regulations_router)
router.include_router(repeatmasker_router)
router.include_router(chipseq_router)
router.include_router(overlap_track_router)


@router.get("/config/{species_id}", response_model=IGVConfigResponse)
@rate_limit("60/minute")
def get_igv_config(
    request: Request,
    species_id: int,
    db: Session = Depends(get_db),
):
    """
    获取指定物种的 IGV.js 配置

    Args:
        species_id: 物种 ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)

    Returns:
        IGV.js 完整配置，包含参考基因组和默认轨道
    """
    # 验证物种存在
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # 获取基因组参考
    try:
        reference = get_genome_reference(species_id)
    except HTTPException:
        raise HTTPException(
            status_code=404,
            detail=f"IGV configuration not available for species: {species.display_name}"
        )

    # 构建轨道列表
    tracks = []

    # FANTOM CAT transcripts 轨道 (仅 Human)
    # 使用 BED12 bigBed 格式，包含完整的外显子结构（block信息）
    # 在 IGV 中可以看到外显子/内含子结构，而不仅仅是单个区块
    # 只有当 GENOMES_DIR 配置且存在时才添加此轨道
    genomes_dir_available = settings.GENOMES_DIR and os.path.exists(settings.GENOMES_DIR)
    if species_id == 1 and genomes_dir_available:
        fantom_transcripts_track = IGVTrack(
            name="FANTOM CAT lncRNA Transcripts",
            type="annotation",
            format="bigbed",
            url="/genomes/fantom_cat_transcripts_bed12.bb",
            indexURL=None,
            displayMode="EXPANDED",  # EXPANDED 模式显示基因名标签
            color="#4A90D9",  # 蓝色系
            height=150,  # 增加高度以更好展示外显子结构和标签
            visibilityWindow=None,  # bigBed 自动处理可见窗口
            labelFields="name",  # 使用 BED12 的 name 字段（第4列）作为标签
            defaultLabelFields="name",  # 默认显示 name 字段
            expandedRowHeight=25,  # 展开模式下每行高度
        )
        tracks.append(fantom_transcripts_track)

    # 基因注释轨道 (非人类灵长类物种)
    # 使用从 Ensembl GTF 转换的 BigBed 格式，包含完整的外显子结构
    # 只有当 GENOMES_DIR 配置且存在时才添加此轨道
    if species_id in GENE_ANNOTATION_TRACKS and genomes_dir_available:
        gene_track_config = GENE_ANNOTATION_TRACKS[species_id]
        gene_annotation_track = IGVTrack(
            name=gene_track_config["name"],
            type="annotation",
            format="bigbed",
            url=gene_track_config["url"],
            indexURL=None,
            displayMode="EXPANDED",  # EXPANDED 模式显示基因结构
            color="#2E7D32",  # 绿色系，区分于其他轨道
            height=150,  # 增加高度以更好展示外显子结构
            visibilityWindow=None,  # bigBed 自动处理可见窗口
            labelFields="name",  # 使用转录本 ID 作为标签
            defaultLabelFields="name",
            expandedRowHeight=25,  # 展开模式下每行高度
        )
        tracks.append(gene_annotation_track)

    # 注意：Species Mode 不加载 BED/BEDPE 轨道
    # 原因：全物种数据量约 50 万条记录，无索引的 BED 文件会导致 IGV.js 卡死
    # 用户应该使用 Gene Mode 来查看具体基因的调控关系
    #
    # 如果需要全局浏览调控关系，可以：
    # 1. 将 BED 转换为 BigBed 格式（支持索引）
    # 2. 使用服务端区域过滤
    # 3. 实现 track hub 动态加载

    # 构建搜索配置
    # 使用新的 /api/v1/igv/locus 端点，支持基因名和染色体坐标搜索
    search_config = IGVSearchConfig(
        url=f"/api/v1/igv/locus?q=$FEATURE$&species_id={species_id}",
        chromosomeField="chromosome",
        startField="start",
        endField="end",
    )

    # 构建 IGV 配置
    # 配置策略:
    # 1. 内置基因组 (Human/hg19): fastaURL 和 twoBitURL 都为 None，使用 genome ID
    # 2. 自定义基因组 (其他灵长类): 使用 twoBitURL 或 fastaURL
    if reference.fastaURL is None and reference.twoBitURL is None:
        # 使用内置基因组 ID (如 hg19)
        config = IGVConfig(
            genome=reference.id,  # 如 "hg19"
            reference=None,
            locus="chr1:1-1000000",  # 1Mb 初始视图，加载更快
            tracks=tracks,
            search=search_config,
        )
    else:
        # 使用自定义参考基因组 (优先使用 twoBitURL)
        config = IGVConfig(
            genome=None,
            reference=reference,
            locus="chr1:1-1000000",  # 1Mb 初始视图，加载更快
            tracks=tracks,
            search=search_config,
        )

    return IGVConfigResponse(
        success=True,
        data=config,
        message=f"IGV configuration for {species.display_name} ({reference.id})"
    )


@router.get("/genomes", response_model=list[SpeciesGenomeInfo])
@rate_limit("60/minute")
def list_available_genomes(request: Request, db: Session = Depends(get_db)):
    """
    列出所有可用的基因组配置

    Returns:
        所有支持 IGV 可视化的物种及其基因组信息
    """
    species_list = db.query(Species).all()

    result = []
    for species in species_list:
        if species.species_id in GENOME_REFERENCES:
            ref_data = GENOME_REFERENCES[species.species_id]
            result.append(SpeciesGenomeInfo(
                species_id=species.species_id,
                species_name=species.display_name,
                genome_assembly=species.genome_assembly or ref_data["id"],
                reference=GenomeReference(**ref_data),
                available=True,
            ))
        else:
            # 暂不支持的物种
            result.append(SpeciesGenomeInfo(
                species_id=species.species_id,
                species_name=species.display_name,
                genome_assembly=species.genome_assembly or "unknown",
                reference=GenomeReference(
                    id="unknown",
                    name="Not Available",
                    fastaURL=None,
                    indexURL=None,
                    cytobandURL=None,
                    twoBitURL=None,
                ),
                available=False,
            ))

    return result


@router.get("/config/gene/{gene_name}", response_model=IGVConfigResponse)
@rate_limit("60/minute")
def get_igv_config_for_gene(
    request: Request,
    gene_name: str,
    padding: int = Query(50000, ge=0, le=500000, description="基因两侧扩展区域(bp)"),
    include_chipseq: bool = Query(False, description="Include ChIP-seq tracks"),
    chipseq_marks: Optional[str] = Query(
        None,
        description="Comma-separated ChIP-seq mark types to include, e.g., H3K27me3,H3K4me3. If not specified but include_chipseq=true, all available marks are included."
    ),
    db: Session = Depends(get_db),
):
    """
    获取指定基因的 IGV.js 配置

    自动定位到该基因的基因组位置，并只加载该基因相关的调控关系

    Args:
        gene_name: 基因名称（如 CATG00000000011.1）
        padding: 基因两侧扩展区域，默认 50kb
        include_chipseq: 是否包含 ChIP-seq 轨道（默认 False）
        chipseq_marks: ChIP-seq mark types，逗号分隔（如 H3K27me3,H3K4me3）

    Returns:
        IGV.js 配置，locus 定位到基因位置

    Example:
        GET /api/v1/igv/config/gene/CATG00000000011.1?include_chipseq=true&chipseq_marks=H3K27me3,H3K4me3
    """
    # 查找基因
    gene = (
        db.query(Gene)
        .filter(
            (Gene.gene_name == gene_name) | (Gene.gene_ensembl_id == gene_name)
        )
        .first()
    )

    if not gene:
        raise HTTPException(status_code=404, detail=f"Gene not found: {gene_name}")

    # 获取物种信息
    species = db.query(Species).filter(Species.species_id == gene.species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found for gene: {gene_name}")

    # 检查基因是否有位置信息
    if not gene.chromosome or gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_name} has no genomic coordinates"
        )

    # 获取基因组参考
    try:
        reference = get_genome_reference(species.species_id)
    except HTTPException:
        raise HTTPException(
            status_code=404,
            detail=f"IGV configuration not available for species: {species.display_name}"
        )

    # 计算 locus (基因位置 ± padding)
    start = max(0, gene.gene_start - padding)
    end = gene.gene_end + padding
    locus = f"{gene.chromosome}:{start}-{end}"

    # 构建轨道列表
    tracks = []

    # FANTOM CAT transcripts 轨道 (仅 Human)
    # 使用 BED12 bigBed 格式，包含完整的外显子结构（block信息）
    if species.species_id == 1:
        fantom_transcripts_track = IGVTrack(
            name="FANTOM CAT lncRNA Transcripts",
            type="annotation",
            format="bigbed",
            url="/genomes/fantom_cat_transcripts_bed12.bb",
            indexURL=None,
            displayMode="EXPANDED",  # EXPANDED 模式显示基因名标签
            color="#4A90D9",
            height=150,  # 增加高度以更好展示外显子结构和标签
            visibilityWindow=None,  # bigBed 自动处理可见窗口
            labelFields="name",  # 使用 BED12 的 name 字段（第4列）作为标签
            defaultLabelFields="name",  # 默认显示 name 字段
            expandedRowHeight=25,  # 展开模式下每行高度
        )
        tracks.append(fantom_transcripts_track)

    # 基因注释轨道 (非人类灵长类物种)
    # 使用从 Ensembl GTF 转换的 BigBed 格式
    if species.species_id in GENE_ANNOTATION_TRACKS:
        gene_track_config = GENE_ANNOTATION_TRACKS[species.species_id]
        gene_annotation_track = IGVTrack(
            name=gene_track_config["name"],
            type="annotation",
            format="bigbed",
            url=gene_track_config["url"],
            indexURL=None,
            displayMode="EXPANDED",
            color="#2E7D32",  # 绿色系
            height=150,
            visibilityWindow=None,
            labelFields="name",
            defaultLabelFields="name",
            expandedRowHeight=25,
        )
        tracks.append(gene_annotation_track)

    # 该基因相关的调控关系轨道（按 lncRNA 过滤）
    regulations_track = IGVTrack(
        name=f"Regulations: {gene_name}",
        type="annotation",
        format="bed",
        # 使用 IGV.js webservice 轨道按视窗动态请求，避免一次性加载全基因组数据
        sourceType="service",
        url=f"/api/v1/igv/tracks/regulations/{species.species_id}.bed?lncrna={gene_name}&chr=$CHR&start=$START&end=$END",
        indexURL=None,
        displayMode="EXPANDED",
        color="#FF6B6B",
        height=150,
        visibilityWindow=5000000,  # 5Mb 以上不请求，避免大范围卡顿
    )
    tracks.append(regulations_track)

    # 该基因相关的交互轨道（按 lncRNA 过滤，BEDPE 格式显示弧线连接）
    interactions_track = IGVTrack(
        name=f"Interactions: {gene_name}",
        type="interact",  # IGV.js uses "interact" not "interaction"
        format="bedpe",
        # 使用 webservice 动态加载当前区域交互
        sourceType="service",
        url=f"/api/v1/igv/tracks/interactions/{species.species_id}.bedpe?lncrna={gene_name}&chr=$CHR&start=$START&end=$END",
        indexURL=None,
        displayMode="EXPANDED",
        color="#8B5CF6",  # Purple color for interactions
        height=120,
        visibilityWindow=5000000,  # 5Mb window
    )
    tracks.append(interactions_track)

    # ChIP-seq 轨道（可选）
    # 当 include_chipseq=true 时，添加 ChIP-seq 表观遗传修饰轨道
    chipseq_marks_added = []
    if include_chipseq:
        # Parse requested mark types
        requested_marks = None
        if chipseq_marks:
            requested_marks = [m.strip() for m in chipseq_marks.split(",") if m.strip()]

        # Query available marks for this species

        mark_query = (
            db.query(
                EpigeneticMarkType.mark_name,
                EpigeneticMarkType.mark_category,
                EpigeneticMarkType.display_color,
                EpigeneticMarkType.display_name,
            )
            .join(ChIPSeqExperiment, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .filter(ChIPSeqExperiment.species_id == species.species_id)
            .filter(ChIPSeqExperiment.is_active.is_(True))
        )

        # Filter by requested marks if specified
        if requested_marks:
            mark_query = mark_query.filter(EpigeneticMarkType.mark_name.in_(requested_marks))

        # Get unique marks
        available_marks = mark_query.distinct().order_by(EpigeneticMarkType.mark_name).all()

        # Add ChIP-seq BigBed tracks for Human (species_id=1)
        # Each track contains all marks for a specific cell type
        if species.species_id == 1:
            for cell_type, track_config in CHIPSEQ_BIGBED_TRACKS.items():
                chipseq_track = IGVTrack(
                    name=track_config["name"],
                    type="annotation",
                    format="bigbed",
                    url=track_config["url"],
                    indexURL=None,
                    displayMode="SQUISHED",
                    color=track_config["color"],
                    height=50,
                    visibilityWindow=None,  # BigBed handles its own visibility
                )
                tracks.append(chipseq_track)
                chipseq_marks_added.append(cell_type)
        else:
            # For non-human species, fall back to dynamic API
            for mark in available_marks:
                color = get_chipseq_mark_color(mark.mark_name, mark.display_color)
                track_prefix = get_track_name_prefix(mark.mark_name, mark.mark_category)

                chipseq_track = IGVTrack(
                    name=f"{track_prefix}: {mark.display_name or mark.mark_name}",
                    type="annotation",
                    format="bed",
                    url=f"/api/v1/igv/tracks/chipseq/{species.species_id}.bed?mark_type={mark.mark_name}&chromosome={gene.chromosome}&start={start}&end={end}",
                    indexURL=None,
                    displayMode="SQUISHED",
                    color=color,
                    height=50,
                    visibilityWindow=5000000,
                )
                tracks.append(chipseq_track)
                chipseq_marks_added.append(mark.mark_name)

    # 构建搜索配置
    # Gene Mode 也支持基因搜索，使用相同的搜索 API
    search_config = IGVSearchConfig(
        url=f"/api/v1/igv/locus?q=$FEATURE$&species_id={species.species_id}",
        chromosomeField="chromosome",
        startField="start",
        endField="end",
    )

    # 构建 IGV 配置
    # 配置策略:
    # 1. 内置基因组 (Human/hg19): fastaURL 和 twoBitURL 都为 None，使用 genome ID
    # 2. 自定义基因组 (其他灵长类): 使用 twoBitURL 或 fastaURL
    if reference.fastaURL is None and reference.twoBitURL is None:
        # 使用内置基因组 ID (如 hg19)
        config = IGVConfig(
            genome=reference.id,
            reference=None,
            locus=locus,
            tracks=tracks,
            search=search_config,
        )
    else:
        # 使用自定义参考基因组 (优先使用 twoBitURL)
        config = IGVConfig(
            genome=None,
            reference=reference,
            locus=locus,
            tracks=tracks,
            search=search_config,
        )

    # Build response message
    message = f"IGV configuration for gene {gene_name} at {locus}"
    if chipseq_marks_added:
        message += f" with ChIP-seq marks: {', '.join(chipseq_marks_added)}"

    return IGVConfigResponse(
        success=True,
        data=config,
        message=message
    )


@router.get("/tracks/regulations/{species_id}/count")
@rate_limit("60/minute")
def get_regulations_count(
    request: Request,
    species_id: int,
    chr: Optional[str] = Query(None, description="染色体过滤"),
    start: Optional[int] = Query(None, ge=0, description="起始位置"),
    end: Optional[int] = Query(None, ge=0, description="结束位置"),
    db: Session = Depends(get_db),
):
    """
    获取指定区域的调控关系数量

    用于前端判断是否需要分页加载或显示摘要

    Args:
        species_id: 物种 ID
        chr: 可选，染色体过滤
        start: 可选，起始位置
        end: 可选，结束位置

    Returns:
        区域内的调控关系数量
    """
    # 验证物种存在
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # 仅需计数：使用 func.count 避免 Query.count() 生成子查询带来的额外开销
    query = (
        db.query(func.count(Regulation.regulation_id))
        .filter(Regulation.species_id == species_id)
        .filter(Regulation.best_peak_chr.isnot(None))
    )

    # 区域过滤
    if chr:
        query = query.filter(Regulation.best_peak_chr == chr)

        if start is not None and end is not None:
            query = query.filter(
                and_(
                    Regulation.best_peak_start < end,
                    Regulation.best_peak_end > start,
                )
            )

    count = query.scalar() or 0

    return {
        "success": True,
        "data": {
            "species_id": species_id,
            "species_name": species.display_name,
            "chr": chr,
            "start": start,
            "end": end,
            "count": count,
        },
        "message": f"Found {count} regulations in the specified region",
    }
