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
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.core.config import settings
from app.core.validators import normalize_optional_str, parse_comma_list
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


# =============================================================================
# ChIP-seq IGV Track Endpoints
# =============================================================================

@router.get("/tracks/chipseq/{species_id}.bed")
@rate_limit("60/minute")
def get_chipseq_bed(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID"),
    mark_type: str = Query(..., description="Mark type, e.g., H3K27me3"),
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome, e.g., chr1"),
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
                # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
                "Content-Disposition": content_disposition_attachment(filename),
                "Content-Type": "text/plain; charset=utf-8",
            },
        )

    # Determine max_records: use explicit limit, or default when no region filter
    # Default limit of 50000 when no region filter to prevent loading all 420k peaks
    if limit is not None:
        max_records = limit
    elif normalized_chromosome is None:
        max_records = 50000  # Default limit when no region filter
    else:
        max_records = None  # No limit when region filter is specified

    # Data exists - generate full BED stream
    logger.info(
        f"ChIP-seq BED export: species={species_id}, mark={mark_type}, "
        f"chr={normalized_chromosome}, start={start}, end={end}, max_records={max_records}"
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
