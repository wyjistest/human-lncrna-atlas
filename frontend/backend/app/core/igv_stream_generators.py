"""
IGV数据流生成器
包含BED、BEDPE、RepeatMasker、ChIP-seq数据流生成函数
"""
from typing import Optional, Generator
from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_, func

from app.models import (
    Regulation,
    Gene,
    GenomicFeature,
    ChIPSeqPeak,
    ChIPSeqExperiment,
    EpigeneticMarkType,
)
from app.core.igv_utils import get_repeatmasker_track_id


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

    # 流式处理：使用 yield_per + stream_results 避免 offset 扫描导致的大表性能问题
    batch_size = 10000
    streaming_query = query.execution_options(stream_results=True).yield_per(batch_size)

    for row in streaming_query:
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

    # 流式处理：使用 yield_per + stream_results 避免 offset 扫描
    batch_size = 10000
    streaming_query = query.execution_options(stream_results=True).yield_per(batch_size)

    for row in streaming_query:
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

    # Build query (select only required columns to reduce IO/memory)
    query = (
        db.query(
            GenomicFeature.chromosome,
            GenomicFeature.feature_start,
            GenomicFeature.feature_end,
            GenomicFeature.feature_name,
            GenomicFeature.strand,
            GenomicFeature.attributes,
        )
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

    # Stream results without OFFSET scans (better for large tables / long streams)
    batch_size = 10000
    streaming_query = query.execution_options(stream_results=True).yield_per(batch_size)

    for row in streaming_query:
        # BED coordinates are 0-based, half-open
        chr_name = row.chromosome
        start = row.feature_start
        end = row.feature_end

        # Feature name
        name = row.feature_name or "repeat"

        # Score: convert divergence to 0-1000 scale
        # Lower divergence = more conserved = higher score
        attrs = row.attributes or {}
        divergence = attrs.get("divergence", 50)
        # Score = 1000 - (divergence * 20), clamped to 0-1000
        score = max(0, min(1000, int(1000 - float(divergence) * 20)))

        # Strand
        strand = row.strand or "."

        yield f"{chr_name}\t{start}\t{end}\t{name}\t{score}\t{strand}\n"


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

    # Build query for peaks
    query = (
        db.query(
            ChIPSeqPeak.chromosome,
            ChIPSeqPeak.peak_start,
            ChIPSeqPeak.peak_end,
            ChIPSeqPeak.peak_name,
            ChIPSeqPeak.fold_enrichment,
            ChIPSeqPeak.strand,
            ChIPSeqPeak.neg_log10_pvalue,
            ChIPSeqPeak.neg_log10_qvalue,
        )
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .filter(ChIPSeqPeak.species_id == species_id)
        .filter(ChIPSeqExperiment.species_id == species_id)
        .filter(ChIPSeqExperiment.mark_type_id == mark_type_obj.mark_type_id)
        .filter(ChIPSeqExperiment.is_active.is_(True))
    )

    # Region filter
    if chr_filter:
        query = query.filter(ChIPSeqPeak.chromosome == chr_filter)

        if start_filter is not None and end_filter is not None:
            # Region overlap: peak overlaps with [start_filter, end_filter)
            # PostgreSQL: Use range overlap to leverage GiST index on int8range(peak_start, peak_end, '[)')
            is_postgresql = db.get_bind().dialect.name == "postgresql"
            if is_postgresql:
                query = query.filter(
                    func.int8range(ChIPSeqPeak.peak_start, ChIPSeqPeak.peak_end, "[)")
                    .op("&&")(func.int8range(start_filter, end_filter, "[)"))
                )
            else:
                query = query.filter(
                    and_(
                        ChIPSeqPeak.peak_start < end_filter,
                        ChIPSeqPeak.peak_end > start_filter,
                    )
                )

    # Order by chromosome and position
    query = query.order_by(ChIPSeqPeak.chromosome, ChIPSeqPeak.peak_start)

    # Stream results without OFFSET scans
    batch_size = 10000
    streaming_query = query.execution_options(stream_results=True).yield_per(batch_size)
    peak_counter = 0

    for row in streaming_query:
        peak_counter += 1

        # Check max_records limit
        if max_records is not None and peak_counter > max_records:
            return

        # BED coordinates
        chr_name = row.chromosome
        start = row.peak_start
        end = row.peak_end

        # Name field
        name = row.peak_name or f"{mark_type}_peak{peak_counter}"

        # Score: convert fold_enrichment to 0-1000 scale
        # Typical fold_enrichment ranges from 1 to 50+
        fe = float(row.fold_enrichment) if row.fold_enrichment else 1.0
        score = min(1000, max(0, int(fe * 20)))  # Scale: fe * 20, max 1000

        # Strand (ChIP-seq peaks typically don't have strand info)
        strand = row.strand or "."

        # Signal value (fold_enrichment)
        signal_value = f"{fe:.4f}" if fe else "0"

        # pValue (-log10)
        p_val = float(row.neg_log10_pvalue) if row.neg_log10_pvalue else 0
        p_value_str = f"{p_val:.4f}"

        # qValue (-log10)
        q_val = float(row.neg_log10_qvalue) if row.neg_log10_qvalue else 0
        q_value_str = f"{q_val:.4f}"

        # Output BED9 format line
        yield f"{chr_name}\t{start}\t{end}\t{name}\t{score}\t{strand}\t{signal_value}\t{p_value_str}\t{q_value_str}\n"


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
