"""
Genomic Features API Router
Provides endpoints for RepeatMasker annotations and other genomic features
"""
import logging
from typing import Optional, List
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Float

from app.core.database import get_db
from app.models import Gene, GenomicFeature, FeatureTrack, Species
from app.schemas.features import (
    RepeatMaskerFeature,
    RepeatMaskerResponse,
    RepeatStats,
    RepeatClassDistribution,
    RepeatFamilyDistribution,
    GeneRepeatSummary,
    FeatureTrackResponse,
    FeatureTrackStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])

# Default flanking region size for gene queries (10kb)
DEFAULT_FLANKING_REGION = 10000


def get_repeatmasker_track_id(db: Session) -> int:
    """Get the track_id for RepeatMasker annotations"""
    track = db.query(FeatureTrack).filter(
        FeatureTrack.track_name == 'repeatmasker_repeats'
    ).first()
    if not track:
        raise HTTPException(
            status_code=404,
            detail="RepeatMasker track not found. Please ensure the database schema is initialized."
        )
    return track.track_id


# =============================================================================
# Feature Track Endpoints
# =============================================================================

@router.get("/tracks", response_model=List[FeatureTrackResponse])
def list_feature_tracks(
    category: Optional[str] = Query(None, description="Filter by track category"),
    active_only: bool = Query(True, description="Only return active tracks"),
    db: Session = Depends(get_db),
):
    """
    List all available feature tracks
    """
    query = db.query(FeatureTrack)

    if category:
        query = query.filter(FeatureTrack.track_category == category)
    if active_only:
        query = query.filter(FeatureTrack.is_active == True)

    tracks = query.order_by(FeatureTrack.track_category, FeatureTrack.display_name).all()
    return tracks


# NOTE: /tracks/stats must be defined BEFORE /tracks/{track_id} to avoid routing conflict
@router.get("/tracks/stats", response_model=List[FeatureTrackStats])
def get_feature_track_statistics(
    db: Session = Depends(get_db),
):
    """
    Get statistics for all feature tracks (feature counts by species)
    """
    # Query feature counts grouped by track and species
    stats_query = (
        db.query(
            FeatureTrack.track_id,
            FeatureTrack.track_name,
            FeatureTrack.display_name,
            Species.species_code,
            func.count(GenomicFeature.feature_id).label('count')
        )
        .outerjoin(GenomicFeature, FeatureTrack.track_id == GenomicFeature.track_id)
        .outerjoin(Species, GenomicFeature.species_id == Species.species_id)
        .filter(FeatureTrack.is_active == True)
        .group_by(
            FeatureTrack.track_id,
            FeatureTrack.track_name,
            FeatureTrack.display_name,
            Species.species_code
        )
        .all()
    )

    # Aggregate results by track
    track_stats = {}
    for row in stats_query:
        track_id = row.track_id
        if track_id not in track_stats:
            track_stats[track_id] = {
                'track_id': track_id,
                'track_name': row.track_name,
                'display_name': row.display_name,
                'species_stats': {},
                'total_features': 0
            }
        if row.species_code:
            track_stats[track_id]['species_stats'][row.species_code] = row.count
            track_stats[track_id]['total_features'] += row.count

    return [FeatureTrackStats(**stats) for stats in track_stats.values()]


@router.get("/tracks/{track_id}", response_model=FeatureTrackResponse)
def get_feature_track(
    track_id: int,
    db: Session = Depends(get_db),
):
    """
    Get details for a specific feature track
    """
    track = db.query(FeatureTrack).filter(FeatureTrack.track_id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Feature track not found")
    return track


# =============================================================================
# RepeatMasker Gene Endpoints
# =============================================================================

@router.get("/genes/{gene_id}/repeats", response_model=RepeatMaskerResponse)
def get_gene_repeats(
    gene_id: int,
    repeat_class: Optional[str] = Query(None, description="Filter by repeat class (LINE, SINE, LTR, DNA, etc.)"),
    repeat_family: Optional[str] = Query(None, description="Filter by repeat family (L1, Alu, etc.)"),
    min_divergence: Optional[float] = Query(None, ge=0, le=100, description="Minimum divergence percentage"),
    max_divergence: Optional[float] = Query(None, ge=0, le=100, description="Maximum divergence percentage"),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000, description="Flanking region size in bp"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Get RepeatMasker annotations for a gene region (+/- flanking region)

    Returns repeat elements that overlap with the gene region including flanking regions.
    Default flanking region is 10kb on each side.
    """
    # 1. Query gene information
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # 2. Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    # 3. Get RepeatMasker track_id
    track_id = get_repeatmasker_track_id(db)

    # 4. Calculate query region
    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # 5. Build query conditions
    conditions = [
        GenomicFeature.track_id == track_id,
        GenomicFeature.species_id == gene.species_id,
        GenomicFeature.chromosome == gene.chromosome,
        GenomicFeature.feature_start < region_end,
        GenomicFeature.feature_end > region_start,
    ]

    # Apply filters
    if repeat_class:
        conditions.append(GenomicFeature.attributes['repeat_class'].astext == repeat_class)
    if repeat_family:
        conditions.append(GenomicFeature.attributes['repeat_family'].astext == repeat_family)
    if min_divergence is not None:
        conditions.append(
            cast(GenomicFeature.attributes['divergence'].astext, Float) >= min_divergence
        )
    if max_divergence is not None:
        conditions.append(
            cast(GenomicFeature.attributes['divergence'].astext, Float) <= max_divergence
        )

    # 5. Get total count
    total = db.query(func.count(GenomicFeature.feature_id)).filter(
        and_(*conditions)
    ).scalar() or 0

    # 6. Paginated query
    offset = (page - 1) * page_size
    features = (
        db.query(GenomicFeature)
        .filter(and_(*conditions))
        .order_by(GenomicFeature.feature_start)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # 7. Convert to response format
    items = [RepeatMaskerFeature.from_genomic_feature(f) for f in features]

    return RepeatMaskerResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )


@router.get("/genes/{gene_id}/repeats/stats", response_model=GeneRepeatSummary)
def get_gene_repeat_stats(
    gene_id: int,
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000, description="Flanking region size in bp"),
    db: Session = Depends(get_db),
):
    """
    Get RepeatMasker statistics for a gene region

    Returns aggregated statistics including:
    - Total count and length of repeat elements
    - Coverage percentage
    - Distribution by repeat class and family
    - Divergence statistics
    """
    # 1. Query gene information
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # 2. Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    # 3. Get RepeatMasker track_id
    track_id = get_repeatmasker_track_id(db)

    # 4. Calculate query region
    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking
    region_length = region_end - region_start

    # 5. Base query conditions
    base_conditions = [
        GenomicFeature.track_id == track_id,
        GenomicFeature.species_id == gene.species_id,
        GenomicFeature.chromosome == gene.chromosome,
        GenomicFeature.feature_start < region_end,
        GenomicFeature.feature_end > region_start,
    ]

    # 5. Get all repeats in the region for statistics
    features = db.query(GenomicFeature).filter(and_(*base_conditions)).all()

    if not features:
        # Return empty stats if no repeats found
        return GeneRepeatSummary(
            gene_id=gene_id,
            gene_name=gene.gene_name or "Unknown",
            chromosome=gene.chromosome,
            gene_start=gene.gene_start,
            gene_end=gene.gene_end,
            region_start=region_start,
            region_end=region_end,
            stats=RepeatStats(
                total_count=0,
                total_length=0,
                coverage_percentage=0.0,
                class_distribution=[],
                family_distribution=[],
                avg_divergence=0.0,
                min_divergence=0.0,
                max_divergence=0.0,
            )
        )

    # 6. Calculate statistics
    total_count = len(features)

    # Calculate total length (clipped to region boundaries)
    total_length = 0
    class_counts = {}
    family_counts = {}
    divergences = []

    for f in features:
        # Clip feature to region boundaries
        start = max(f.feature_start, region_start)
        end = min(f.feature_end, region_end)
        total_length += (end - start)

        # Count by class and family
        attrs = f.attributes or {}
        repeat_class = attrs.get('repeat_class', 'Unknown')
        repeat_family = attrs.get('repeat_family', 'Unknown')

        class_counts[repeat_class] = class_counts.get(repeat_class, 0) + 1

        family_key = (repeat_family, repeat_class)
        family_counts[family_key] = family_counts.get(family_key, 0) + 1

        # Collect divergence values
        divergence = attrs.get('divergence')
        if divergence is not None:
            divergences.append(float(divergence))

    # Calculate coverage percentage
    coverage_percentage = (total_length / region_length * 100) if region_length > 0 else 0.0

    # Build class distribution
    class_distribution = [
        RepeatClassDistribution(
            repeat_class=cls,
            count=count,
            percentage=(count / total_count * 100) if total_count > 0 else 0.0
        )
        for cls, count in sorted(class_counts.items(), key=lambda x: -x[1])
    ]

    # Build family distribution (top 10)
    family_distribution = [
        RepeatFamilyDistribution(
            repeat_family=family,
            repeat_class=cls,
            count=count,
            percentage=(count / total_count * 100) if total_count > 0 else 0.0
        )
        for (family, cls), count in sorted(family_counts.items(), key=lambda x: -x[1])[:10]
    ]

    # Calculate divergence statistics
    avg_divergence = sum(divergences) / len(divergences) if divergences else 0.0
    min_divergence = min(divergences) if divergences else 0.0
    max_divergence = max(divergences) if divergences else 0.0

    return GeneRepeatSummary(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        gene_start=gene.gene_start,
        gene_end=gene.gene_end,
        region_start=region_start,
        region_end=region_end,
        stats=RepeatStats(
            total_count=total_count,
            total_length=total_length,
            coverage_percentage=round(coverage_percentage, 2),
            class_distribution=class_distribution,
            family_distribution=family_distribution,
            avg_divergence=round(avg_divergence, 2),
            min_divergence=round(min_divergence, 2),
            max_divergence=round(max_divergence, 2),
        )
    )


# =============================================================================
# Region-based RepeatMasker Endpoints
# =============================================================================

@router.get("/repeats/{species_id}", response_model=RepeatMaskerResponse)
def get_repeats_by_region(
    species_id: int,
    chromosome: str = Query(..., description="Chromosome name"),
    start: int = Query(..., ge=0, description="Region start position"),
    end: int = Query(..., ge=0, description="Region end position"),
    repeat_class: Optional[str] = Query(None, description="Filter by repeat class"),
    repeat_family: Optional[str] = Query(None, description="Filter by repeat family"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Get RepeatMasker annotations for a specific genomic region
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    # Validate region
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    # Get track_id
    track_id = get_repeatmasker_track_id(db)

    # Build query conditions
    conditions = [
        GenomicFeature.track_id == track_id,
        GenomicFeature.species_id == species_id,
        GenomicFeature.chromosome == chromosome,
        GenomicFeature.feature_start < end,
        GenomicFeature.feature_end > start,
    ]

    if repeat_class:
        conditions.append(GenomicFeature.attributes['repeat_class'].astext == repeat_class)
    if repeat_family:
        conditions.append(GenomicFeature.attributes['repeat_family'].astext == repeat_family)

    # Get total count
    total = db.query(func.count(GenomicFeature.feature_id)).filter(
        and_(*conditions)
    ).scalar() or 0

    # Paginated query
    offset = (page - 1) * page_size
    features = (
        db.query(GenomicFeature)
        .filter(and_(*conditions))
        .order_by(GenomicFeature.feature_start)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [RepeatMaskerFeature.from_genomic_feature(f) for f in features]

    return RepeatMaskerResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Repeat Class/Family List Endpoints
# =============================================================================

@router.get("/repeats/{species_id}/classes", response_model=List[str])
def get_repeat_classes(
    species_id: int,
    db: Session = Depends(get_db),
):
    """
    Get list of unique repeat classes for a species
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    track_id = get_repeatmasker_track_id(db)

    # Query distinct repeat classes
    result = (
        db.query(GenomicFeature.attributes['repeat_class'].astext.label('repeat_class'))
        .filter(
            GenomicFeature.track_id == track_id,
            GenomicFeature.species_id == species_id,
        )
        .distinct()
        .all()
    )

    classes = sorted([r.repeat_class for r in result if r.repeat_class])
    return classes


@router.get("/repeats/{species_id}/families", response_model=List[str])
def get_repeat_families(
    species_id: int,
    repeat_class: Optional[str] = Query(None, description="Filter by repeat class"),
    db: Session = Depends(get_db),
):
    """
    Get list of unique repeat families for a species
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    track_id = get_repeatmasker_track_id(db)

    # Build query
    query = (
        db.query(GenomicFeature.attributes['repeat_family'].astext.label('repeat_family'))
        .filter(
            GenomicFeature.track_id == track_id,
            GenomicFeature.species_id == species_id,
        )
    )

    if repeat_class:
        query = query.filter(GenomicFeature.attributes['repeat_class'].astext == repeat_class)

    result = query.distinct().all()

    families = sorted([r.repeat_family for r in result if r.repeat_family])
    return families
