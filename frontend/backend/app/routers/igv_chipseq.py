"""
IGV ChIP-seq轨道路由
提供ChIP-seq峰的BED格式数据导出和配置

Phase 9.11: 使用共享验证器进行输入验证
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.core.config import settings
from app.core.validators import normalize_optional_str, parse_comma_list
from app.core.utils import sanitize_for_log
from app.models import Species, ChIPSeqExperiment, EpigeneticMarkType
from app.core.igv_stream_generators import (
    generate_chipseq_bed_stream,
    generate_empty_chipseq_bed_stream,
)
from app.core.igv_utils import get_chipseq_mark_color, get_genome_reference
from app.config.igv_genomes import (
    get_track_name_prefix,
    CHIPSEQ_BIGBED_TRACKS,
    GENE_ANNOTATION_TRACKS,
)
from app.schemas.igv import IGVTrack, IGVConfigResponse, IGVConfig, IGVSearchConfig
from app.utils.http_headers import content_disposition_attachment

logger = logging.getLogger(__name__)

router = APIRouter()

# 10Mb 以内允许 IGV 区域查询，避免一次请求拖垮数据库/连接池
MAX_REGION_SIZE_BP = 10_000_000

# 无区域过滤（chromosome/start/end 未同时提供）时的默认返回上限：
# - 防止 “整条染色体/全表” 流式导出被滥用为 DoS
DEFAULT_MAX_RECORDS_NO_REGION = 50_000

# 显式 limit 的上限（用于交互式轨道；批量导出请走专用 export 接口）
MAX_LIMIT = 100_000


# =============================================================================
# ChIP-seq IGV Track Endpoints
# =============================================================================

@router.get("/chipseq/marks/{species_id}")
@rate_limit("60/minute")
def get_igv_chipseq_marks(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID"),
    db: Session = Depends(get_db),
):
    """
    获取 IGV Genome Browser 可用的表观基因组 marks 列表。

    说明：
    - 前端用于决定哪些 marks 可以被选择并加载为轨道。
    - 返回值使用标准 wrapper：{ success, data, message }。
    - 优先尝试使用物化视图 mv_chipseq_mark_stats（更快）；不可用时回退到直接聚合查询。
    """
    cache_key = cache.make_key("igv:chipseq_marks", species_id=species_id)
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    marks: list[dict] = []

    # Fast path: materialized view (if available)
    try:
        mv_stmt = text(
            """
            SELECT
                m.mark_name,
                m.display_name,
                m.mark_category,
                m.display_color,
                m.description,
                s.experiment_count,
                s.total_peaks
            FROM mv_chipseq_mark_stats s
            JOIN epigenetic_mark_types m ON s.mark_name = m.mark_name
            WHERE s.species_code = :species_code
              AND m.is_active = TRUE
            ORDER BY m.sort_order, m.mark_name
            """
        )
        rows = db.execute(mv_stmt, {"species_code": species.species_code}).fetchall()
        for row in rows:
            marks.append(
                {
                    "mark_name": row[0],
                    "display_name": row[1] or row[0],
                    "mark_category": row[2],
                    "display_color": row[3] or "#666666",
                    "description": row[4],
                    "experiment_count": int(row[5] or 0),
                    "peak_count": int(row[6] or 0),
                }
            )
    except Exception as e:
        # Fallback below (best-effort; avoid failing the whole endpoint)
        logger.debug(
            "mv_chipseq_mark_stats unavailable for species_id=%s species_code=%s: %s",
            species_id,
            sanitize_for_log(species.species_code),
            sanitize_for_log(e),
            exc_info=True,
        )
        marks = []

    # Fallback: direct aggregation (slower on large peak tables; cached by TTL)
    if not marks:
        query = text(
            """
            SELECT DISTINCT
                m.mark_name,
                m.display_name,
                m.mark_category,
                m.display_color,
                m.description,
                COUNT(DISTINCT e.experiment_id) AS experiment_count,
                COUNT(p.peak_id) AS peak_count
            FROM epigenetic_mark_types m
            JOIN chipseq_experiments e ON m.mark_type_id = e.mark_type_id
            LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
            WHERE e.species_id = :species_id
              AND e.is_active = TRUE
              AND m.is_active = TRUE
            GROUP BY m.mark_name, m.display_name, m.mark_category, m.display_color, m.description
            HAVING COUNT(DISTINCT e.experiment_id) > 0
            ORDER BY MIN(m.sort_order), m.mark_name
            """
        )
        try:
            rows = db.execute(query, {"species_id": species_id}).fetchall()
        except Exception as e:
            logger.warning(
                "Failed to aggregate chipseq marks for species_id=%s: %s",
                species_id,
                sanitize_for_log(e),
                exc_info=True,
            )
            raise
        for row in rows:
            marks.append(
                {
                    "mark_name": row[0],
                    "display_name": row[1] or row[0],
                    "mark_category": row[2],
                    "display_color": row[3] or "#666666",
                    "description": row[4],
                    "experiment_count": int(row[5] or 0),
                    "peak_count": int(row[6] or 0),
                }
            )

    result = {
        "success": True,
        "data": {
            "species_id": species_id,
            "species_name": species.display_name,
            "marks": marks,
        },
        "message": f"Available epigenomic marks for {species.display_name}: {len(marks)}",
    }
    cache.set(cache_key, result, cache.TTL_STATS)
    return result


@router.get("/tracks/chipseq/{species_id}.bed")
@rate_limit("60/minute")
def get_chipseq_bed(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID"),
    mark_type: str = Query(..., min_length=1, max_length=64, description="Mark type, e.g., H3K27me3"),
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome, e.g., chr1"),
    start: Optional[int] = Query(None, ge=0, description="Region start position (0-based)"),
    end: Optional[int] = Query(None, ge=0, description="Region end position"),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max records to return (default: {DEFAULT_MAX_RECORDS_NO_REGION} when no region filter)",
    ),
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

    normalized_chromosome = normalize_optional_str(chromosome)

    # Parameter validation
    if (start is not None or end is not None) and normalized_chromosome is None:
        raise HTTPException(
            status_code=400,
            detail="chromosome parameter is required when using start/end filters"
        )

    if start is not None and end is not None and start >= end:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    if start is not None and end is not None and (end - start) > MAX_REGION_SIZE_BP:
        raise HTTPException(
            status_code=400,
            detail=f"region too large (max {MAX_REGION_SIZE_BP} bp)",
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
        # 仅需判断是否存在数据：用 LIMIT 1 替代 COUNT(*)，减少数据库开销
        experiment = (
            db.query(ChIPSeqExperiment.experiment_id)
            .filter(ChIPSeqExperiment.species_id == species_id)
            .filter(ChIPSeqExperiment.mark_type_id == mark_type_obj.mark_type_id)
            .filter(ChIPSeqExperiment.is_active.is_(True))
            .first()
        )
        has_data = experiment is not None

    # Build filename
    filename = f"chipseq_{mark_type}_species{species_id}"
    if normalized_chromosome:
        filename += f"_{normalized_chromosome}"
        if start is not None and end is not None:
            filename += f"_{start}-{end}"
    filename += ".bed"

    # If no data exists, return empty BED file with header (200 OK)
    # This allows IGV.js to load the track without errors
    if not has_data:
        logger.info(
            "ChIP-seq BED export (no data): species=%s, mark=%s - returning empty BED file",
            species_id,
            sanitize_for_log(mark_type),
        )

        empty_stream = generate_empty_chipseq_bed_stream(
            mark_type=mark_type,
            species_name=species.display_name,
        )

        return StreamingResponse(
            empty_stream,
            media_type="text/plain",
            headers={
                # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
                "Content-Disposition": content_disposition_attachment(filename),
                "Content-Type": "text/plain; charset=utf-8",
            },
        )

    # Determine max_records:
    # - Use explicit limit when provided.
    # - Apply a conservative default when the request is not a bounded region query
    #   (chromosome/start/end not all provided) to prevent whole-chromosome streaming DoS.
    # - Only disable the default limit for bounded region queries (<= 10Mb).
    has_region_filter = normalized_chromosome is not None and start is not None and end is not None
    if limit is not None:
        max_records = limit
    elif not has_region_filter:
        max_records = DEFAULT_MAX_RECORDS_NO_REGION
    else:
        max_records = None

    # Data exists - generate full BED stream
    logger.info(
        "ChIP-seq BED export: species=%s, mark=%s, chr=%s, start=%s, end=%s, max_records=%s",
        species_id,
        sanitize_for_log(mark_type),
        sanitize_for_log(normalized_chromosome),
        start,
        end,
        max_records,
    )

    bed_stream = generate_chipseq_bed_stream(
        db=db,
        species_id=species_id,
        mark_type=mark_type,
        chr_filter=normalized_chromosome,
        start_filter=start,
        end_filter=end,
        max_records=max_records,
    )

    return StreamingResponse(
        bed_stream,
        media_type="text/plain",
        headers={
            # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
            "Content-Disposition": content_disposition_attachment(filename),
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.get("/config/chipseq/{species_id}", response_model=IGVConfigResponse)
@rate_limit("60/minute")
def get_igv_chipseq_config(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID"),
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

    # Parse requested mark types (Phase 9.11: 使用共享验证器)
    requested_marks = parse_comma_list(mark_types, param_name="mark_types")

    # Query available marks for this species

    mark_query = (
        db.query(
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            EpigeneticMarkType.display_name,
        )
        .join(ChIPSeqExperiment, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .filter(ChIPSeqExperiment.species_id == species_id)
        .filter(ChIPSeqExperiment.is_active.is_(True))
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
    # Only add local file tracks when GENOMES_DIR is configured
    genomes_dir_available = settings.GENOMES_DIR and os.path.exists(settings.GENOMES_DIR)
    if species_id == 1 and genomes_dir_available:
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
    elif species_id in GENE_ANNOTATION_TRACKS and genomes_dir_available:
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

    # Add ChIP-seq BigBed tracks for Human (species_id=1)
    # Each track contains all marks for a specific cell type
    # The BigBed files use BED9 format with itemRgb for mark-specific colors
    if species_id == 1:
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
    else:
        # For non-human species, fall back to dynamic API (if marks available)
        for mark in available_marks:
            color = get_chipseq_mark_color(mark.mark_name, mark.display_color)
            track_prefix = get_track_name_prefix(mark.mark_name, mark.mark_category)

            chipseq_track = IGVTrack(
                name=f"{track_prefix}: {mark.display_name or mark.mark_name}",
                type="annotation",
                format="bed",
                url=f"/api/v1/igv/tracks/chipseq/{species_id}.bed?mark_type={mark.mark_name}",
                indexURL=None,
                displayMode="SQUISHED",
                color=color,
                height=50,
                visibilityWindow=5000000,
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


# =============================================================================
# lncRNA-ChIP-seq Overlap Track Endpoint
# =============================================================================
