"""
IGV RepeatMasker轨道路由
提供重复序列注释的BED格式数据导出和配置
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models import Species, GenomicFeature, FeatureTrack
from app.core.igv_stream_generators import generate_repeatmasker_bed_stream
from app.schemas.igv import IGVTrack

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# RepeatMasker IGV Track Endpoints
# =============================================================================

def get_repeatmasker_track_id(db: Session) -> Optional[int]:
    """Get the track_id for RepeatMasker annotations"""
    track = db.query(FeatureTrack).filter(
        FeatureTrack.track_name == 'repeatmasker_repeats'
    ).first()
    return track.track_id if track else None


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
