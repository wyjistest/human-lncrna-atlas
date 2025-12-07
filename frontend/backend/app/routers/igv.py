"""
IGV.js 集成 API 路由
提供基因组浏览器配置和 BED 格式数据导出
"""
import logging
from typing import Optional, Generator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_

from app.core.database import get_db
from app.models import Regulation, Gene, Species, GenomicFeature, FeatureTrack, ChIPSeqExperiment, ChIPSeqPeak, EpigeneticMarkType
from app.schemas.igv import (
    GenomeReference,
    IGVTrack,
    IGVConfig,
    IGVConfigResponse,
    SpeciesGenomeInfo,
    IGVSearchResult,
    IGVSearchConfig,
    GeneAutocompleteItem,
    GeneAutocompleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/igv", tags=["igv"])

# =============================================================================
# ChIP-seq Mark Colors Configuration
# =============================================================================
# Default colors for common histone modifications
# These are used when mark colors are not defined in the database (epigenetic_mark_types.display_color)
CHIPSEQ_MARK_COLORS = {
    "H3K27me3": "#9B59B6",  # Purple - Repressive mark (Polycomb complex)
    "H3K4me1": "#F39C12",   # Orange - Enhancer mark
    "H3K4me3": "#27AE60",   # Green - Active promoter
    "H3K27ac": "#3498DB",   # Blue - Active enhancer
    "H3K36me3": "#1ABC9C",  # Teal - Transcription elongation
    "H3K9me3": "#E74C3C",   # Red - Heterochromatin/repressive
    "H3K9ac": "#3498DB",    # Blue - Active transcription
    "H3K4me2": "#27AE60",   # Green - Active chromatin
    "H3K79me2": "#1ABC9C",  # Teal - Transcription elongation
    "H2AZ": "#8E44AD",      # Dark purple - Variant histone
    "H3K56ac": "#2980B9",   # Dark blue - Transcription/repair
    "DNase-HS": "#FF6B35",  # Orange-red - Open chromatin (DNase-seq)
}

# Default color for unknown mark types
DEFAULT_CHIPSEQ_COLOR = "#7F8C8D"  # Gray


def get_track_name_prefix(mark_name: str, mark_category: Optional[str] = None) -> str:
    """
    Get the appropriate track name prefix based on mark type/category.

    - DNase-HS → "Open Chromatin"
    - ATAC-seq (future) → "Open Chromatin"
    - Others → "ChIP-seq"
    """
    # Open chromatin assays
    if mark_name in ("DNase-HS", "ATAC-seq"):
        return "Open Chromatin"
    if mark_category == "other" and "DNase" in mark_name:
        return "Open Chromatin"
    # Default to ChIP-seq for histone modifications
    return "ChIP-seq"

# =============================================================================
# Genome Reference Configuration
# =============================================================================
# 基因组参考配置
# 版本与项目数据一致: hg19, panTro5, rheMac10, calJac3
#
# 配置策略:
# - Human (hg19): 使用 IGV.js 内置基因组 ID，自动从 IGV 服务器加载
# - 其他灵长类: 使用 UCSC 2bit 格式，支持 HTTP Range 请求实现快速随机访问
#
# 2bit 格式优势 (相比 .fa.gz):
# - 支持 byte-range 请求，只下载需要的序列片段
# - 不需要全文件下载，加载速度快
# - IGV.js 原生支持 UCSC 2bit 格式
#
# 注意：IGV.js 内置支持的基因组列表见 https://igv.org/genomes/genomes.json
GENOME_REFERENCES = {
    1: {  # Human (hg19/GRCh37) - IGV.js 内置支持
        "id": "hg19",
        "name": "Human (GRCh37/hg19)",
        "fastaURL": None,  # Use built-in genome
        "indexURL": None,
        "cytobandURL": None,
        "twoBitURL": None,  # Not needed for built-in genome
    },
    2: {  # Chimp (panTro5) - Use 2bit format for better performance
        "id": "panTro5",
        "name": "Chimpanzee (Pan_tro_2.1.4/panTro5)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": "/genomes/cytoBand.panTro5.txt.gz",  # Local path
        "twoBitURL": "/genomes/panTro5.2bit",  # Local path
    },
    3: {  # Macaque (rheMac10) - Use 2bit format for better performance
        "id": "rheMac10",
        "name": "Rhesus Macaque (Mmul_10/rheMac10)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": "/genomes/cytoBand.rheMac10.txt.gz",  # Local path
        "twoBitURL": "/genomes/rheMac10.2bit",  # Local path
    },
    4: {  # Marmoset (calJac3) - Use 2bit format for better performance
        "id": "calJac3",
        "name": "Marmoset (Callithrix_jacchus-3.2/calJac3)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": None,  # calJac3 does not have cytoBand data in UCSC
        "twoBitURL": "/genomes/calJac3.2bit",  # Local path
    },
}

# 物种名称映射
SPECIES_NAMES = {
    1: "Human",
    2: "Chimpanzee",
    3: "Rhesus Macaque",
    4: "Marmoset",
}

# 基因注释轨道配置
# 每个物种的基因注释 BigBed 文件路径
GENE_ANNOTATION_TRACKS = {
    2: {  # Chimpanzee (panTro5)
        "name": "Ensembl Genes (Pan_tro_3.0)",
        "url": "/genomes/panTro5_genes.bb",
        "description": "Gene annotations from Ensembl release 97",
    },
    3: {  # Macaque (rheMac10)
        "name": "Ensembl Genes (Mmul_10)",
        "url": "/genomes/rheMac10_genes.bb",
        "description": "Gene annotations from Ensembl release 98",
    },
    4: {  # Marmoset (calJac3)
        "name": "Ensembl Genes (C_jacchus3.2.1)",
        "url": "/genomes/calJac3_genes.bb",
        "description": "Gene annotations from Ensembl release 78",
    },
}


def get_genome_reference(species_id: int) -> GenomeReference:
    """获取指定物种的基因组参考配置"""
    if species_id not in GENOME_REFERENCES:
        raise HTTPException(
            status_code=404,
            detail=f"Genome reference not found for species_id: {species_id}"
        )

    ref_data = GENOME_REFERENCES[species_id]
    return GenomeReference(**ref_data)


def get_chipseq_mark_color(mark_name: str, db_color: Optional[str] = None) -> str:
    """
    Get the display color for a ChIP-seq mark type.

    Priority:
    1. Database-defined color (from epigenetic_mark_types.display_color)
    2. Predefined color in CHIPSEQ_MARK_COLORS
    3. Default gray color

    Args:
        mark_name: The mark type name (e.g., H3K27me3)
        db_color: Color from database (if available)

    Returns:
        Hex color code (e.g., #9B59B6)
    """
    if db_color and db_color != '#666666':  # Skip default gray
        return db_color
    return CHIPSEQ_MARK_COLORS.get(mark_name, DEFAULT_CHIPSEQ_COLOR)


@router.get("/config/{species_id}", response_model=IGVConfigResponse)
def get_igv_config(
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
    if species_id == 1:
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
    if species_id in GENE_ANNOTATION_TRACKS:
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
def list_available_genomes(db: Session = Depends(get_db)):
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


def generate_bed_stream(
    db: Session,
    species_id: int,
    chr_filter: Optional[str] = None,
    start_filter: Optional[int] = None,
    end_filter: Optional[int] = None,
    lncrna_filter: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    生成 BED 格式数据流

    BED6 格式: chr, start, end, name, score, strand
    - name: lncRNA_name->target_name
    - score: binding_affinity (scaled to 0-1000 for BED format)
    - strand: . (unknown/both)

    注意：BED 坐标是 0-based, half-open [start, end)
    """
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")

    # 构建基础查询
    query = (
        db.query(
            Regulation.best_peak_chr,
            Regulation.best_peak_start,
            Regulation.best_peak_end,
            Regulation.binding_affinity,
            LncRNAGene.gene_name.label("lncrna_name"),
            TargetGene.gene_name.label("target_name"),
        )
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .filter(Regulation.species_id == species_id)
        .filter(Regulation.best_peak_chr.isnot(None))
    )

    # lncRNA 过滤（按基因名或 Ensembl ID）
    if lncrna_filter:
        query = query.filter(
            (LncRNAGene.gene_name == lncrna_filter) |
            (LncRNAGene.gene_ensembl_id == lncrna_filter)
        )

    # 区域过滤
    if chr_filter:
        query = query.filter(Regulation.best_peak_chr == chr_filter)

        if start_filter is not None and end_filter is not None:
            # 区域查询：查找与指定区域重叠的记录
            # 重叠条件: region.start < peak.end AND region.end > peak.start
            query = query.filter(
                and_(
                    Regulation.best_peak_start < end_filter,
                    Regulation.best_peak_end > start_filter,
                )
            )

    # 按染色体和起始位置排序
    query = query.order_by(Regulation.best_peak_chr, Regulation.best_peak_start)

    # 流式处理，分批获取
    batch_size = 10000
    offset = 0

    while True:
        batch = query.offset(offset).limit(batch_size).all()
        if not batch:
            break

        for row in batch:
            # BED 坐标转换（数据库中已经是 0-based）
            chr_name = row.best_peak_chr
            start = row.best_peak_start
            end = row.best_peak_end

            # 构建 name 字段
            lncrna = row.lncrna_name or "unknown_lncRNA"
            target = row.target_name or "unknown_target"
            name = f"{lncrna}->{target}"

            # 转换 binding_affinity 到 BED score (0-1000)
            # 原始值范围假设是 0-100，需要放大 10 倍
            ba = float(row.binding_affinity) if row.binding_affinity else 0
            score = min(1000, max(0, int(ba * 10)))

            # strand 未知，使用 '.'
            strand = "."

            # 输出 BED6 格式行
            yield f"{chr_name}\t{start}\t{end}\t{name}\t{score}\t{strand}\n"

        offset += batch_size

        # 如果返回的记录少于批次大小，说明已经到末尾
        if len(batch) < batch_size:
            break


def generate_bedpe_stream(
    db: Session,
    species_id: int,
    chr_filter: Optional[str] = None,
    start_filter: Optional[int] = None,
    end_filter: Optional[int] = None,
    lncrna_filter: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    生成 BEDPE 格式数据流用于 IGV.js 交互轨道

    BEDPE 格式: chr1, start1, end1, chr2, start2, end2, name, score
    - Endpoint 1 (chr1/start1/end1): lncRNA 基因位置 (通过 lncrna_gene_id JOIN genes 表)
    - Endpoint 2 (chr2/start2/end2): 结合位点位置 (best_peak_chr, best_peak_start, best_peak_end)
    - name: lncRNA_name|target_name
    - score: binding_affinity (scaled to 0-1000 for BEDPE format)

    注意：BEDPE 坐标是 0-based, half-open [start, end)
    """
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")

    # 构建基础查询
    # Endpoint 1: lncRNA 基因位置
    # Endpoint 2: 结合位点位置
    query = (
        db.query(
            # Endpoint 1: lncRNA gene location
            LncRNAGene.chromosome.label("chr1"),
            LncRNAGene.gene_start.label("start1"),
            LncRNAGene.gene_end.label("end1"),
            # Endpoint 2: binding site
            Regulation.best_peak_chr.label("chr2"),
            Regulation.best_peak_start.label("start2"),
            Regulation.best_peak_end.label("end2"),
            # Metadata
            LncRNAGene.gene_name.label("lncrna_name"),
            TargetGene.gene_name.label("target_name"),
            Regulation.binding_affinity,
        )
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .filter(Regulation.species_id == species_id)
        # 跳过 lncRNA 基因没有坐标的记录
        .filter(LncRNAGene.chromosome.isnot(None))
        .filter(LncRNAGene.gene_start.isnot(None))
        .filter(LncRNAGene.gene_end.isnot(None))
        # 跳过 best_peak_chr 为空的记录
        .filter(Regulation.best_peak_chr.isnot(None))
        .filter(Regulation.best_peak_start.isnot(None))
        .filter(Regulation.best_peak_end.isnot(None))
    )

    # lncRNA 过滤（按基因名或 Ensembl ID）
    if lncrna_filter:
        query = query.filter(
            (LncRNAGene.gene_name == lncrna_filter) |
            (LncRNAGene.gene_ensembl_id == lncrna_filter)
        )

    # 区域过滤 - 检查两个 endpoint 是否与指定区域重叠
    if chr_filter:
        # 区域过滤：至少一个 endpoint 在指定区域内
        chr_filter_condition = (
            (LncRNAGene.chromosome == chr_filter) |
            (Regulation.best_peak_chr == chr_filter)
        )
        query = query.filter(chr_filter_condition)

        if start_filter is not None and end_filter is not None:
            # 区域查询：查找任一 endpoint 与指定区域重叠的记录
            # 重叠条件: region.start < endpoint.end AND region.end > endpoint.start
            region_overlap_condition = (
                # Endpoint 1 (lncRNA gene) overlaps with region
                (
                    (LncRNAGene.chromosome == chr_filter) &
                    (LncRNAGene.gene_start < end_filter) &
                    (LncRNAGene.gene_end > start_filter)
                ) |
                # Endpoint 2 (binding site) overlaps with region
                (
                    (Regulation.best_peak_chr == chr_filter) &
                    (Regulation.best_peak_start < end_filter) &
                    (Regulation.best_peak_end > start_filter)
                )
            )
            query = query.filter(region_overlap_condition)

    # 按 lncRNA 染色体和起始位置排序
    query = query.order_by(LncRNAGene.chromosome, LncRNAGene.gene_start)

    # 流式处理，分批获取
    batch_size = 10000
    offset = 0

    while True:
        batch = query.offset(offset).limit(batch_size).all()
        if not batch:
            break

        for row in batch:
            # Endpoint 1: lncRNA gene location
            chr1 = row.chr1
            start1 = row.start1
            end1 = row.end1

            # Endpoint 2: binding site location
            chr2 = row.chr2
            start2 = row.start2
            end2 = row.end2

            # 构建 name 字段 (使用 | 分隔符)
            lncrna = row.lncrna_name or "unknown_lncRNA"
            target = row.target_name or "unknown_target"
            name = f"{lncrna}|{target}"

            # 转换 binding_affinity 到 BEDPE score (0-1000)
            # 原始值范围假设是 0-100，需要放大 10 倍
            ba = float(row.binding_affinity) if row.binding_affinity else 0
            score = min(1000, max(0, int(ba * 10)))

            # 输出 BEDPE 8列格式行
            yield f"{chr1}\t{start1}\t{end1}\t{chr2}\t{start2}\t{end2}\t{name}\t{score}\n"

        offset += batch_size

        # 如果返回的记录少于批次大小，说明已经到末尾
        if len(batch) < batch_size:
            break


@router.get("/tracks/regulations/{species_id}.bed")
def get_regulations_bed(
    species_id: int,
    chr: Optional[str] = Query(None, description="染色体过滤，如 chr1"),
    start: Optional[int] = Query(None, ge=0, description="起始位置 (0-based)"),
    end: Optional[int] = Query(None, ge=0, description="结束位置"),
    lncrna: Optional[str] = Query(None, description="lncRNA 基因名过滤，如 CATG00000000011.1"),
    db: Session = Depends(get_db),
):
    """
    流式导出调控关系为 BED 格式

    BED6 格式: chr, start, end, name, score, strand
    - name: lncRNA_name->target_name
    - score: binding_affinity (0-1000)
    - strand: . (unknown)

    支持区域查询和 lncRNA 过滤，优化 IGV 加载性能

    Args:
        species_id: 物种 ID
        chr: 可选，染色体过滤
        start: 可选，起始位置
        end: 可选，结束位置
        lncrna: 可选，lncRNA 基因名过滤（只返回该 lncRNA 的调控关系）

    Returns:
        StreamingResponse with BED format data
    """
    # 验证物种存在
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # 参数验证
    if (start is not None or end is not None) and chr is None:
        raise HTTPException(
            status_code=400,
            detail="chr parameter is required when using start/end filters"
        )

    if start is not None and end is not None and start >= end:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    logger.info(f"BED export requested: species={species_id}, chr={chr}, start={start}, end={end}, lncrna={lncrna}")

    # 生成 BED 数据流
    bed_stream = generate_bed_stream(
        db=db,
        species_id=species_id,
        chr_filter=chr,
        start_filter=start,
        end_filter=end,
        lncrna_filter=lncrna,
    )

    # 设置响应头
    filename = f"regulations_species{species_id}"
    if lncrna:
        filename = f"regulations_{lncrna}"
    if chr:
        filename += f"_{chr}"
        if start is not None and end is not None:
            filename += f"_{start}-{end}"
    filename += ".bed"

    return StreamingResponse(
        bed_stream,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.get("/tracks/interactions/{species_id}.bedpe")
def get_interactions_bedpe(
    species_id: int,
    chr: Optional[str] = Query(None, description="染色体过滤，如 chr1"),
    start: Optional[int] = Query(None, ge=0, description="起始位置 (0-based)"),
    end: Optional[int] = Query(None, ge=0, description="结束位置"),
    lncrna: Optional[str] = Query(None, description="lncRNA 基因名过滤，如 CATG00000000011.1"),
    db: Session = Depends(get_db),
):
    """
    流式导出 lncRNA-Target 交互为 BEDPE 格式

    BEDPE 格式用于 IGV.js 的 interact 轨道，显示 lncRNA 与其结合位点之间的弧线连接。

    BEDPE 8列格式: chr1, start1, end1, chr2, start2, end2, name, score
    - Endpoint 1 (chr1/start1/end1): lncRNA 基因位置
    - Endpoint 2 (chr2/start2/end2): 结合位点位置 (best_peak)
    - name: lncRNA_name|target_name
    - score: binding_affinity (0-1000)

    支持区域查询和 lncRNA 过滤，优化 IGV 加载性能

    Args:
        species_id: 物种 ID
        chr: 可选，染色体过滤（匹配任一 endpoint）
        start: 可选，起始位置
        end: 可选，结束位置
        lncrna: 可选，lncRNA 基因名过滤（只返回该 lncRNA 的交互）

    Returns:
        StreamingResponse with BEDPE format data
    """
    # 验证物种存在
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # 参数验证
    if (start is not None or end is not None) and chr is None:
        raise HTTPException(
            status_code=400,
            detail="chr parameter is required when using start/end filters"
        )

    if start is not None and end is not None and start >= end:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    logger.info(f"BEDPE export requested: species={species_id}, chr={chr}, start={start}, end={end}, lncrna={lncrna}")

    # 生成 BEDPE 数据流
    bedpe_stream = generate_bedpe_stream(
        db=db,
        species_id=species_id,
        chr_filter=chr,
        start_filter=start,
        end_filter=end,
        lncrna_filter=lncrna,
    )

    # 设置响应头
    filename = f"interactions_species{species_id}"
    if lncrna:
        filename = f"interactions_{lncrna}"
    if chr:
        filename += f"_{chr}"
        if start is not None and end is not None:
            filename += f"_{start}-{end}"
    filename += ".bedpe"

    return StreamingResponse(
        bedpe_stream,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.get("/config/gene/{gene_name}", response_model=IGVConfigResponse)
def get_igv_config_for_gene(
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
        url=f"/api/v1/igv/tracks/regulations/{species.species_id}.bed?lncrna={gene_name}",
        indexURL=None,
        displayMode="EXPANDED",
        color="#FF6B6B",
        height=150,
    )
    tracks.append(regulations_track)

    # 该基因相关的交互轨道（按 lncRNA 过滤，BEDPE 格式显示弧线连接）
    interactions_track = IGVTrack(
        name=f"Interactions: {gene_name}",
        type="interact",  # IGV.js uses "interact" not "interaction"
        format="bedpe",
        url=f"/api/v1/igv/tracks/interactions/{species.species_id}.bedpe?lncrna={gene_name}",
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
        from sqlalchemy import func

        mark_query = (
            db.query(
                EpigeneticMarkType.mark_name,
                EpigeneticMarkType.mark_category,
                EpigeneticMarkType.display_color,
                EpigeneticMarkType.display_name,
            )
            .join(ChIPSeqExperiment, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .filter(ChIPSeqExperiment.species_id == species.species_id)
            .filter(ChIPSeqExperiment.is_active == True)
        )

        # Filter by requested marks if specified
        if requested_marks:
            mark_query = mark_query.filter(EpigeneticMarkType.mark_name.in_(requested_marks))

        # Get unique marks
        available_marks = mark_query.distinct().order_by(EpigeneticMarkType.mark_name).all()

        # Add ChIP-seq/Open Chromatin tracks for each mark type
        for mark in available_marks:
            color = get_chipseq_mark_color(mark.mark_name, mark.display_color)
            track_prefix = get_track_name_prefix(mark.mark_name, mark.mark_category)

            chipseq_track = IGVTrack(
                name=f"{track_prefix}: {mark.display_name or mark.mark_name}",
                type="annotation",
                format="bed",
                url=f"/api/v1/igv/tracks/chipseq/{species.species_id}.bed?mark_type={mark.mark_name}",
                indexURL=None,
                displayMode="SQUISHED",  # SQUISHED for ChIP-seq peaks
                color=color,
                height=50,
                visibilityWindow=5000000,  # 5Mb visibility window
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
def get_regulations_count(
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

    # 构建查询
    query = (
        db.query(Regulation)
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

    count = query.count()

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


# =============================================================================
# RepeatMasker IGV Track Endpoints
# =============================================================================

def get_repeatmasker_track_id(db: Session) -> Optional[int]:
    """Get the track_id for RepeatMasker annotations"""
    track = db.query(FeatureTrack).filter(
        FeatureTrack.track_name == 'repeatmasker_repeats'
    ).first()
    return track.track_id if track else None


def generate_repeatmasker_bed_stream(
    db: Session,
    species_id: int,
    chr_filter: Optional[str] = None,
    start_filter: Optional[int] = None,
    end_filter: Optional[int] = None,
) -> Generator[str, None, None]:
    """
    Generate RepeatMasker BED format data stream

    BED6 format: chr, start, end, name, score, strand
    - name: repeat_name (e.g., AluSx, L1M2)
    - score: divergence scaled to 0-1000 (lower divergence = higher score)
    - strand: +/-/.
    """
    track_id = get_repeatmasker_track_id(db)
    if not track_id:
        return

    # Build query
    query = (
        db.query(GenomicFeature)
        .filter(GenomicFeature.track_id == track_id)
        .filter(GenomicFeature.species_id == species_id)
    )

    # Region filter
    if chr_filter:
        query = query.filter(GenomicFeature.chromosome == chr_filter)

        if start_filter is not None and end_filter is not None:
            query = query.filter(
                and_(
                    GenomicFeature.feature_start < end_filter,
                    GenomicFeature.feature_end > start_filter,
                )
            )

    # Order by chromosome and position
    query = query.order_by(GenomicFeature.chromosome, GenomicFeature.feature_start)

    # Stream data in batches
    batch_size = 10000
    offset = 0

    while True:
        batch = query.offset(offset).limit(batch_size).all()
        if not batch:
            break

        for feature in batch:
            # BED coordinates are 0-based, half-open
            chr_name = feature.chromosome
            start = feature.feature_start
            end = feature.feature_end

            # Feature name
            name = feature.feature_name or "repeat"

            # Score: convert divergence to 0-1000 scale
            # Lower divergence = more conserved = higher score
            attrs = feature.attributes or {}
            divergence = attrs.get('divergence', 50)
            # Score = 1000 - (divergence * 20), clamped to 0-1000
            score = max(0, min(1000, int(1000 - float(divergence) * 20)))

            # Strand
            strand = feature.strand or '.'

            yield f"{chr_name}\t{start}\t{end}\t{name}\t{score}\t{strand}\n"

        offset += batch_size

        if len(batch) < batch_size:
            break


@router.get("/tracks/repeatmasker/{species_id}.bed")
def get_repeatmasker_bed(
    species_id: int,
    chr: Optional[str] = Query(None, description="Chromosome filter, e.g., chr1"),
    start: Optional[int] = Query(None, ge=0, description="Start position (0-based)"),
    end: Optional[int] = Query(None, ge=0, description="End position"),
    db: Session = Depends(get_db),
):
    """
    Stream RepeatMasker annotations as BED format for IGV.js

    BED6 format: chr, start, end, name, score, strand
    - name: repeat element name (e.g., AluSx, L1M2)
    - score: conservation score (lower divergence = higher score)
    - strand: +/-/.

    Supports region queries for efficient loading.

    Args:
        species_id: Species ID
        chr: Optional chromosome filter
        start: Optional start position
        end: Optional end position

    Returns:
        StreamingResponse with BED format data
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # Validate RepeatMasker track exists
    track_id = get_repeatmasker_track_id(db)
    if not track_id:
        raise HTTPException(
            status_code=404,
            detail="RepeatMasker track not found. Please ensure the database schema is initialized."
        )

    # Parameter validation
    if (start is not None or end is not None) and chr is None:
        raise HTTPException(
            status_code=400,
            detail="chr parameter is required when using start/end filters"
        )

    if start is not None and end is not None and start >= end:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    logger.info(f"RepeatMasker BED export: species={species_id}, chr={chr}, start={start}, end={end}")

    # Generate BED stream
    bed_stream = generate_repeatmasker_bed_stream(
        db=db,
        species_id=species_id,
        chr_filter=chr,
        start_filter=start,
        end_filter=end,
    )

    # Build filename
    filename = f"repeatmasker_species{species_id}"
    if chr:
        filename += f"_{chr}"
        if start is not None and end is not None:
            filename += f"_{start}-{end}"
    filename += ".bed"

    return StreamingResponse(
        bed_stream,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.get("/tracks/repeatmasker/{species_id}/count")
def get_repeatmasker_count(
    species_id: int,
    chr: Optional[str] = Query(None, description="Chromosome filter"),
    start: Optional[int] = Query(None, ge=0, description="Start position"),
    end: Optional[int] = Query(None, ge=0, description="End position"),
    db: Session = Depends(get_db),
):
    """
    Get the count of RepeatMasker features in a region

    Used by frontend to determine loading strategy.

    Args:
        species_id: Species ID
        chr: Optional chromosome filter
        start: Optional start position
        end: Optional end position

    Returns:
        Feature count in the specified region
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    track_id = get_repeatmasker_track_id(db)
    if not track_id:
        return {
            "success": True,
            "data": {
                "species_id": species_id,
                "species_name": species.display_name,
                "count": 0,
                "message": "RepeatMasker track not found"
            }
        }

    # Build query
    query = (
        db.query(GenomicFeature)
        .filter(GenomicFeature.track_id == track_id)
        .filter(GenomicFeature.species_id == species_id)
    )

    # Region filter
    if chr:
        query = query.filter(GenomicFeature.chromosome == chr)

        if start is not None and end is not None:
            query = query.filter(
                and_(
                    GenomicFeature.feature_start < end,
                    GenomicFeature.feature_end > start,
                )
            )

    count = query.count()

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
        "message": f"Found {count} RepeatMasker features in the specified region",
    }


@router.get("/config/repeatmasker/{species_id}")
def get_repeatmasker_igv_config(
    species_id: int,
    display_mode: str = Query(
        "SQUISHED",
        description="Display mode: SQUISHED (default, single color), EXPANDED (colored by repeat class), or COLLAPSED",
        regex="^(SQUISHED|EXPANDED|COLLAPSED)$"
    ),
    db: Session = Depends(get_db),
):
    """
    Get IGV.js track configuration for RepeatMasker

    Returns a track configuration object that can be added to IGV.js.

    Display modes:
    - SQUISHED (default): Compact view with single color, uses BED6 bigBed
    - EXPANDED: Full view with colors by repeat class (UCSC-style), uses BED9 bigBed with itemRGB
    - COLLAPSED: Most compact view, single line

    Args:
        species_id: Species ID
        display_mode: Display mode (SQUISHED, EXPANDED, COLLAPSED)

    Returns:
        IGV.js track configuration
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    track_id = get_repeatmasker_track_id(db)
    if not track_id:
        raise HTTPException(
            status_code=404,
            detail="RepeatMasker track not found. Please ensure the database schema is initialized."
        )

    # Select bigBed file based on display mode
    # EXPANDED mode uses BED9 format with itemRGB for colored display by repeat_class
    # SQUISHED/COLLAPSED modes use BED6 format with single color
    if display_mode == "EXPANDED":
        bigbed_url = "/genomes/repeatmasker_human_bed9.bb"
        use_item_rgb = True
        track_height = 300  # Larger height for UCSC full-like display
        track_color = None  # Use itemRGB colors
        description_suffix = "colored by repeat class (UCSC Full mode)"
        # UCSC Full mode settings
        expanded_row_height = 10  # Smaller rows to fit more elements
        max_rows = 1000  # Allow more rows
    else:
        bigbed_url = "/genomes/repeatmasker_human.bb"
        use_item_rgb = False
        track_height = 50 if display_mode == "SQUISHED" else 30
        track_color = "#E67E22"  # Orange
        description_suffix = "single color mode"
        expanded_row_height = None
        max_rows = None

    # Build track configuration
    track_config = {
        "name": "RepeatMasker",
        "type": "annotation",
        "format": "bigbed",
        "url": bigbed_url,
        "displayMode": display_mode,
        "height": track_height,
        "autoHeight": True if display_mode == "EXPANDED" else False,  # Auto-expand height
        "minHeight": 50,
        "maxHeight": 500 if display_mode == "EXPANDED" else 100,
        "visibilityWindow": -1,  # Always show features regardless of zoom
        "description": f"RepeatMasker annotations for {species.display_name} ({description_suffix})",
    }

    # Add EXPANDED mode specific settings
    if expanded_row_height:
        track_config["expandedRowHeight"] = expanded_row_height
    if max_rows:
        track_config["maxRows"] = max_rows

    # Add color configuration
    if use_item_rgb:
        # Enable itemRGB parsing for BED9 format
        # IGV.js uses the RGB values from column 9 (itemRgb field)
        track_config["useItemRgb"] = True
    else:
        track_config["color"] = track_color

    return {
        "success": True,
        "data": track_config,
        "message": f"RepeatMasker IGV track configuration for {species.display_name} (mode: {display_mode})"
    }


@router.get("/config/repeatmasker-classes/{species_id}")
def get_repeatmasker_class_tracks(
    species_id: int,
    db: Session = Depends(get_db),
):
    """
    Get IGV.js track configurations for RepeatMasker grouped by repeat class

    Returns 7 separate track configurations, one for each major repeat class:
    - SINE (red)
    - LINE (blue)
    - LTR (green)
    - DNA (purple)
    - Simple_repeat (black)
    - Low_complexity (gray)
    - Other (dark gray)

    This enables UCSC Genome Browser "full" mode style display where each
    repeat class is shown in a separate track with its own color.

    Args:
        species_id: Species ID (currently only Human/1 is supported)

    Returns:
        List of IGV.js track configurations, one per repeat class
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # Currently only Human (species_id=1) is supported
    if species_id != 1:
        raise HTTPException(
            status_code=400,
            detail=f"RepeatMasker class tracks are currently only available for Human (species_id=1)"
        )

    track_id = get_repeatmasker_track_id(db)
    if not track_id:
        raise HTTPException(
            status_code=404,
            detail="RepeatMasker track not found. Please ensure the database schema is initialized."
        )

    # Define repeat class configurations
    # Colors match UCSC Genome Browser standard colors
    repeat_class_configs = [
        {
            "id": "repeatmasker_SINE",
            "name": "SINE Repeats",
            "url": "/genomes/repeatmasker_SINE.bb",
            "color": "#FF0000",  # Red
            "description": "Short Interspersed Nuclear Elements (SINEs) including Alu elements",
        },
        {
            "id": "repeatmasker_LINE",
            "name": "LINE Repeats",
            "url": "/genomes/repeatmasker_LINE.bb",
            "color": "#0000CC",  # Blue
            "description": "Long Interspersed Nuclear Elements (LINEs) including L1 elements",
        },
        {
            "id": "repeatmasker_LTR",
            "name": "LTR Repeats",
            "url": "/genomes/repeatmasker_LTR.bb",
            "color": "#00CC00",  # Green
            "description": "Long Terminal Repeat (LTR) retrotransposons",
        },
        {
            "id": "repeatmasker_DNA",
            "name": "DNA Repeats",
            "url": "/genomes/repeatmasker_DNA.bb",
            "color": "#CC00CC",  # Purple/Magenta
            "description": "DNA transposons",
        },
        {
            "id": "repeatmasker_Simple",
            "name": "Simple Repeats",
            "url": "/genomes/repeatmasker_Simple.bb",
            "color": "#000000",  # Black
            "description": "Simple tandem repeats (microsatellites)",
        },
        {
            "id": "repeatmasker_LowComplexity",
            "name": "Low Complexity",
            "url": "/genomes/repeatmasker_LowComplexity.bb",
            "color": "#666666",  # Gray
            "description": "Low complexity regions",
        },
        {
            "id": "repeatmasker_Other",
            "name": "Other Repeats",
            "url": "/genomes/repeatmasker_Other.bb",
            "color": "#888888",  # Dark gray
            "description": "Other repeat classes (RNA, Satellite, etc.)",
        },
    ]

    # Build track configurations
    tracks = []
    for config in repeat_class_configs:
        track = {
            "id": config["id"],
            "name": config["name"],
            "type": "annotation",
            "format": "bigbed",
            "url": config["url"],
            "displayMode": "SQUISHED",  # Compact view by default
            "color": config["color"],
            "height": 50,
            "autoHeight": False,
            "minHeight": 30,
            "maxHeight": 200,
            "visibilityWindow": -1,  # Always show features
            "description": config["description"],
            "useItemRgb": True,  # Use colors from BED9 itemRgb field
        }
        tracks.append(track)

    return {
        "success": True,
        "data": {
            "tracks": tracks,
            "species_id": species_id,
            "species_name": species.display_name,
        },
        "message": f"RepeatMasker class-grouped tracks for {species.display_name} (7 tracks)"
    }


# =============================================================================
# ChIP-seq IGV Track Endpoints
# =============================================================================

@router.get("/chipseq/marks/{species_id}")
def get_available_chipseq_marks(
    species_id: int,
    db: Session = Depends(get_db),
):
    """
    Get available ChIP-seq mark types for a species

    Returns the list of histone modifications that have been imported for the given species,
    along with their display colors and experiment counts.

    Args:
        species_id: Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)

    Returns:
        List of available mark types with metadata

    Example Response:
    ```json
    {
        "success": true,
        "data": {
            "species_id": 1,
            "species_name": "Human",
            "marks": [
                {
                    "mark_name": "H3K27me3",
                    "mark_category": "repressive",
                    "display_color": "#9B59B6",
                    "experiment_count": 5,
                    "peak_count": 125000
                }
            ]
        }
    }
    ```
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # Query available marks for this species
    # Join experiments with mark types and count experiments per mark
    from sqlalchemy import func

    mark_stats = (
        db.query(
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            EpigeneticMarkType.display_name,
            EpigeneticMarkType.description,
            func.count(ChIPSeqExperiment.experiment_id).label("experiment_count"),
        )
        .join(ChIPSeqExperiment, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .filter(ChIPSeqExperiment.species_id == species_id)
        .filter(ChIPSeqExperiment.is_active == True)
        .group_by(
            EpigeneticMarkType.mark_type_id,
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            EpigeneticMarkType.display_name,
            EpigeneticMarkType.description,
        )
        .order_by(EpigeneticMarkType.mark_name)
        .all()
    )

    # Build response
    marks = []
    for row in mark_stats:
        # Get peak count for this mark (optional, can be expensive)
        peak_count_result = (
            db.query(func.count(ChIPSeqPeak.peak_id))
            .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
            .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .filter(ChIPSeqExperiment.species_id == species_id)
            .filter(EpigeneticMarkType.mark_name == row.mark_name)
            .filter(ChIPSeqExperiment.is_active == True)
            .scalar()
        )

        marks.append({
            "mark_name": row.mark_name,
            "display_name": row.display_name,
            "mark_category": row.mark_category,
            "display_color": get_chipseq_mark_color(row.mark_name, row.display_color),
            "description": row.description,
            "experiment_count": row.experiment_count,
            "peak_count": peak_count_result or 0,
        })

    return {
        "success": True,
        "data": {
            "species_id": species_id,
            "species_name": species.display_name,
            "marks": marks,
            "total_marks": len(marks),
        },
        "message": f"Found {len(marks)} ChIP-seq mark types for {species.display_name}",
    }


def generate_chipseq_bed_stream(
    db: Session,
    species_id: int,
    mark_type: str,
    chr_filter: Optional[str] = None,
    start_filter: Optional[int] = None,
    end_filter: Optional[int] = None,
    max_records: Optional[int] = None,
) -> Generator[str, None, None]:
    """
    Generate ChIP-seq peaks as BED9 format data stream

    BED9 format: chr, start, end, name, score, strand, signalValue, pValue, qValue
    - name: peak_name or mark_type_peakN
    - score: scaled from fold_enrichment (0-1000)
    - strand: . (ChIP-seq peaks typically don't have strand)
    - signalValue: fold_enrichment
    - pValue: -log10(pvalue)
    - qValue: -log10(qvalue)

    Note: BED coordinates are 0-based, half-open [start, end)
    """
    # Get mark type ID
    mark_type_obj = (
        db.query(EpigeneticMarkType)
        .filter(EpigeneticMarkType.mark_name == mark_type)
        .first()
    )
    if not mark_type_obj:
        return

    # Get experiment IDs for this mark and species
    experiment_ids = (
        db.query(ChIPSeqExperiment.experiment_id)
        .filter(ChIPSeqExperiment.species_id == species_id)
        .filter(ChIPSeqExperiment.mark_type_id == mark_type_obj.mark_type_id)
        .filter(ChIPSeqExperiment.is_active == True)
        .all()
    )
    exp_ids = [e.experiment_id for e in experiment_ids]

    if not exp_ids:
        return

    # Build query for peaks
    query = (
        db.query(ChIPSeqPeak)
        .filter(ChIPSeqPeak.species_id == species_id)
        .filter(ChIPSeqPeak.experiment_id.in_(exp_ids))
    )

    # Region filter
    if chr_filter:
        query = query.filter(ChIPSeqPeak.chromosome == chr_filter)

        if start_filter is not None and end_filter is not None:
            # Region overlap: peak overlaps with [start_filter, end_filter)
            query = query.filter(
                and_(
                    ChIPSeqPeak.peak_start < end_filter,
                    ChIPSeqPeak.peak_end > start_filter,
                )
            )

    # Order by chromosome and position
    query = query.order_by(ChIPSeqPeak.chromosome, ChIPSeqPeak.peak_start)

    # Stream data in batches
    batch_size = 10000
    offset = 0
    peak_counter = 0

    while True:
        batch = query.offset(offset).limit(batch_size).all()
        if not batch:
            break

        for peak in batch:
            peak_counter += 1

            # Check max_records limit
            if max_records is not None and peak_counter > max_records:
                return

            # BED coordinates
            chr_name = peak.chromosome
            start = peak.peak_start
            end = peak.peak_end

            # Name field
            name = peak.peak_name or f"{mark_type}_peak{peak_counter}"

            # Score: convert fold_enrichment to 0-1000 scale
            # Typical fold_enrichment ranges from 1 to 50+
            fe = float(peak.fold_enrichment) if peak.fold_enrichment else 1.0
            score = min(1000, max(0, int(fe * 20)))  # Scale: fe * 20, max 1000

            # Strand (ChIP-seq peaks typically don't have strand info)
            strand = peak.strand or "."

            # Signal value (fold_enrichment)
            signal_value = f"{fe:.4f}" if fe else "0"

            # pValue (-log10)
            p_val = float(peak.neg_log10_pvalue) if peak.neg_log10_pvalue else 0
            p_value_str = f"{p_val:.4f}"

            # qValue (-log10)
            q_val = float(peak.neg_log10_qvalue) if peak.neg_log10_qvalue else 0
            q_value_str = f"{q_val:.4f}"

            # Output BED9 format line
            yield f"{chr_name}\t{start}\t{end}\t{name}\t{score}\t{strand}\t{signal_value}\t{p_value_str}\t{q_value_str}\n"

        offset += batch_size

        # Check max_records limit after batch
        if max_records is not None and peak_counter >= max_records:
            return

        if len(batch) < batch_size:
            break


def generate_empty_chipseq_bed_stream(
    mark_type: str,
    species_name: str,
) -> Generator[str, None, None]:
    """
    Generate an empty BED file with header comment.

    This is used when no data exists for a mark type, allowing IGV.js
    to load an empty track without errors (returns 200 instead of 404).

    Args:
        mark_type: The mark type name (e.g., H3K9me3)
        species_name: Species display name for the header
    """
    # BED track header comment
    yield f"# track name=\"ChIP-seq: {mark_type}\" description=\"No data available for {species_name}\"\n"
    # No data rows - file ends here


@router.get("/tracks/chipseq/{species_id}.bed")
def get_chipseq_bed(
    species_id: int,
    mark_type: str = Query(..., description="Mark type, e.g., H3K27me3"),
    chromosome: Optional[str] = Query(None, description="Filter by chromosome, e.g., chr1"),
    start: Optional[int] = Query(None, ge=0, description="Region start position (0-based)"),
    end: Optional[int] = Query(None, ge=0, description="Region end position"),
    limit: Optional[int] = Query(None, ge=1, le=100000, description="Max records to return (default: 50000 when no region filter)"),
    db: Session = Depends(get_db),
):
    """
    Stream ChIP-seq peaks as BED format for IGV.js

    BED9 format: chr, start, end, name, score, strand, signalValue, pValue, qValue
    - name: peak identifier
    - score: fold enrichment scaled to 0-1000
    - strand: . (typically no strand for ChIP-seq)
    - signalValue: original fold enrichment
    - pValue: -log10(p-value)
    - qValue: -log10(q-value)

    Supports region queries for efficient IGV loading.

    IMPORTANT: If the mark_type has no data for the species, this endpoint returns
    an empty BED file (200 OK) with a header comment, NOT a 404 error.
    This allows IGV.js to load empty tracks gracefully without initialization failures.

    Args:
        species_id: Species ID
        mark_type: Histone modification type (required)
        chromosome: Optional chromosome filter
        start: Optional start position
        end: Optional end position

    Returns:
        StreamingResponse with BED9 format data (may be empty with header if no data)

    Example:
        GET /api/v1/igv/tracks/chipseq/1.bed?mark_type=H3K27me3&chromosome=chr1&start=0&end=10000000
    """
    # Validate species - 404 is appropriate for non-existent species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # Parameter validation
    if (start is not None or end is not None) and chromosome is None:
        raise HTTPException(
            status_code=400,
            detail="chromosome parameter is required when using start/end filters"
        )

    if start is not None and end is not None and start >= end:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    # Check if mark_type exists in database
    mark_type_obj = (
        db.query(EpigeneticMarkType)
        .filter(EpigeneticMarkType.mark_name == mark_type)
        .first()
    )

    # Check if experiments exist for this species/mark combination
    has_data = False
    if mark_type_obj:
        experiment_count = (
            db.query(ChIPSeqExperiment)
            .filter(ChIPSeqExperiment.species_id == species_id)
            .filter(ChIPSeqExperiment.mark_type_id == mark_type_obj.mark_type_id)
            .filter(ChIPSeqExperiment.is_active == True)
            .count()
        )
        has_data = experiment_count > 0

    # Build filename
    filename = f"chipseq_{mark_type}_species{species_id}"
    if chromosome:
        filename += f"_{chromosome}"
        if start is not None and end is not None:
            filename += f"_{start}-{end}"
    filename += ".bed"

    # If no data exists, return empty BED file with header (200 OK)
    # This allows IGV.js to load the track without errors
    if not has_data:
        logger.info(
            f"ChIP-seq BED export (no data): species={species_id}, mark={mark_type} - "
            f"returning empty BED file"
        )

        empty_stream = generate_empty_chipseq_bed_stream(
            mark_type=mark_type,
            species_name=species.display_name,
        )

        return StreamingResponse(
            empty_stream,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "text/plain; charset=utf-8",
            },
        )

    # Determine max_records: use explicit limit, or default when no region filter
    # Default limit of 50000 when no region filter to prevent loading all 420k peaks
    if limit is not None:
        max_records = limit
    elif chromosome is None:
        max_records = 50000  # Default limit when no region filter
    else:
        max_records = None  # No limit when region filter is specified

    # Data exists - generate full BED stream
    logger.info(
        f"ChIP-seq BED export: species={species_id}, mark={mark_type}, "
        f"chr={chromosome}, start={start}, end={end}, max_records={max_records}"
    )

    bed_stream = generate_chipseq_bed_stream(
        db=db,
        species_id=species_id,
        mark_type=mark_type,
        chr_filter=chromosome,
        start_filter=start,
        end_filter=end,
        max_records=max_records,
    )

    return StreamingResponse(
        bed_stream,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.get("/config/chipseq/{species_id}", response_model=IGVConfigResponse)
def get_igv_chipseq_config(
    species_id: int,
    mark_types: Optional[str] = Query(
        None,
        description="Comma-separated mark types to include, e.g., H3K27me3,H3K4me3. If not specified, all available marks are included."
    ),
    db: Session = Depends(get_db),
):
    """
    Get IGV.js configuration with ChIP-seq tracks

    Returns a complete IGV configuration including tracks for the specified
    (or all available) ChIP-seq mark types for the given species.

    Each mark type gets its own track with a distinct color.

    Args:
        species_id: Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
        mark_types: Optional comma-separated list of mark types to include

    Returns:
        IGVConfigResponse with genome reference and ChIP-seq tracks

    Example:
        GET /api/v1/igv/config/chipseq/1?mark_types=H3K27me3,H3K4me3
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # Get genome reference
    try:
        reference = get_genome_reference(species_id)
    except HTTPException:
        raise HTTPException(
            status_code=404,
            detail=f"IGV configuration not available for species: {species.display_name}"
        )

    # Parse requested mark types
    requested_marks = None
    if mark_types:
        requested_marks = [m.strip() for m in mark_types.split(",") if m.strip()]

    # Query available marks for this species
    from sqlalchemy import func

    mark_query = (
        db.query(
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            EpigeneticMarkType.display_name,
        )
        .join(ChIPSeqExperiment, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .filter(ChIPSeqExperiment.species_id == species_id)
        .filter(ChIPSeqExperiment.is_active == True)
    )

    # Filter by requested marks if specified
    if requested_marks:
        mark_query = mark_query.filter(EpigeneticMarkType.mark_name.in_(requested_marks))

    # Get unique marks
    available_marks = mark_query.distinct().order_by(EpigeneticMarkType.mark_name).all()

    if not available_marks:
        if requested_marks:
            raise HTTPException(
                status_code=404,
                detail=f"No ChIP-seq data found for marks: {mark_types} in {species.display_name}"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No ChIP-seq data available for {species.display_name}"
            )

    # Build tracks
    tracks = []

    # Add base annotation tracks first (FANTOM CAT for Human, Ensembl for others)
    if species_id == 1:
        fantom_transcripts_track = IGVTrack(
            name="FANTOM CAT lncRNA Transcripts",
            type="annotation",
            format="bigbed",
            url="/genomes/fantom_cat_transcripts_bed12.bb",
            indexURL=None,
            displayMode="EXPANDED",
            color="#4A90D9",
            height=150,
            visibilityWindow=None,
            labelFields="name",
            defaultLabelFields="name",
            expandedRowHeight=25,
        )
        tracks.append(fantom_transcripts_track)
    elif species_id in GENE_ANNOTATION_TRACKS:
        gene_track_config = GENE_ANNOTATION_TRACKS[species_id]
        gene_annotation_track = IGVTrack(
            name=gene_track_config["name"],
            type="annotation",
            format="bigbed",
            url=gene_track_config["url"],
            indexURL=None,
            displayMode="EXPANDED",
            color="#2E7D32",
            height=150,
            visibilityWindow=None,
            labelFields="name",
            defaultLabelFields="name",
            expandedRowHeight=25,
        )
        tracks.append(gene_annotation_track)

    # Add ChIP-seq/Open Chromatin tracks for each mark type
    for mark in available_marks:
        color = get_chipseq_mark_color(mark.mark_name, mark.display_color)
        track_prefix = get_track_name_prefix(mark.mark_name, mark.mark_category)

        chipseq_track = IGVTrack(
            name=f"{track_prefix}: {mark.display_name or mark.mark_name}",
            type="annotation",
            format="bed",
            url=f"/api/v1/igv/tracks/chipseq/{species_id}.bed?mark_type={mark.mark_name}",
            indexURL=None,
            displayMode="SQUISHED",  # SQUISHED for ChIP-seq peaks
            color=color,
            height=50,
            visibilityWindow=5000000,  # 5Mb visibility window
        )
        tracks.append(chipseq_track)

    # Build search config
    search_config = IGVSearchConfig(
        url=f"/api/v1/igv/locus?q=$FEATURE$&species_id={species_id}",
        chromosomeField="chromosome",
        startField="start",
        endField="end",
    )

    # Build IGV config
    if reference.fastaURL is None and reference.twoBitURL is None:
        # Built-in genome (e.g., hg19)
        config = IGVConfig(
            genome=reference.id,
            reference=None,
            locus="chr1:1-1000000",
            tracks=tracks,
            search=search_config,
        )
    else:
        # Custom genome reference
        config = IGVConfig(
            genome=None,
            reference=reference,
            locus="chr1:1-1000000",
            tracks=tracks,
            search=search_config,
        )

    mark_names = [m.mark_name for m in available_marks]
    return IGVConfigResponse(
        success=True,
        data=config,
        message=f"IGV ChIP-seq configuration for {species.display_name} with marks: {', '.join(mark_names)}"
    )
