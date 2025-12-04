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
from app.models import Regulation, Gene, Species
from app.schemas.igv import (
    GenomeReference,
    IGVTrack,
    IGVConfig,
    IGVConfigResponse,
    SpeciesGenomeInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/igv", tags=["igv"])

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
        "cytobandURL": "https://hgdownload.soe.ucsc.edu/goldenPath/panTro5/database/cytoBand.txt.gz",
        "twoBitURL": "https://hgdownload.soe.ucsc.edu/goldenPath/panTro5/bigZips/panTro5.2bit",
    },
    3: {  # Macaque (rheMac10) - Use 2bit format for better performance
        "id": "rheMac10",
        "name": "Rhesus Macaque (Mmul_10/rheMac10)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": "https://hgdownload.soe.ucsc.edu/goldenPath/rheMac10/database/cytoBand.txt.gz",
        "twoBitURL": "https://hgdownload.soe.ucsc.edu/goldenPath/rheMac10/bigZips/rheMac10.2bit",
    },
    4: {  # Marmoset (calJac3) - Use 2bit format for better performance
        "id": "calJac3",
        "name": "Marmoset (Callithrix_jacchus-3.2/calJac3)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": None,  # calJac3 does not have cytoBand data in UCSC
        "twoBitURL": "https://hgdownload.soe.ucsc.edu/goldenPath/calJac3/bigZips/calJac3.2bit",
    },
}

# 物种名称映射
SPECIES_NAMES = {
    1: "Human",
    2: "Chimpanzee",
    3: "Rhesus Macaque",
    4: "Marmoset",
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

    # 注意：Species Mode 不加载 BED/BEDPE 轨道
    # 原因：全物种数据量约 50 万条记录，无索引的 BED 文件会导致 IGV.js 卡死
    # 用户应该使用 Gene Mode 来查看具体基因的调控关系
    #
    # 如果需要全局浏览调控关系，可以：
    # 1. 将 BED 转换为 BigBed 格式（支持索引）
    # 2. 使用服务端区域过滤
    # 3. 实现 track hub 动态加载

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
        )
    else:
        # 使用自定义参考基因组 (优先使用 twoBitURL)
        config = IGVConfig(
            genome=None,
            reference=reference,
            locus="chr1:1-1000000",  # 1Mb 初始视图，加载更快
            tracks=tracks,
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
    db: Session = Depends(get_db),
):
    """
    获取指定基因的 IGV.js 配置

    自动定位到该基因的基因组位置，并只加载该基因相关的调控关系

    Args:
        gene_name: 基因名称（如 CATG00000000011.1）
        padding: 基因两侧扩展区域，默认 50kb

    Returns:
        IGV.js 配置，locus 定位到基因位置
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

    # ��建轨道列表
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
        )
    else:
        # 使用自定义参考基因组 (优先使用 twoBitURL)
        config = IGVConfig(
            genome=None,
            reference=reference,
            locus=locus,
            tracks=tracks,
        )

    return IGVConfigResponse(
        success=True,
        data=config,
        message=f"IGV configuration for gene {gene_name} at {locus}"
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
