"""
ChIP-seq Epigenetic Marks API Router
Provides unified endpoints for multiple histone modifications
"""
import logging
import statistics
from typing import Optional, List, Dict, Any, Tuple
from math import ceil
from itertools import combinations
import io
import csv

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, cast, Float, text
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.database import get_db
from app.models import Gene, Species
from app.schemas.chipseq import (
    # Enums
    MarkType,
    MarkCategory,
    OverlapType,
    ExportFormat,
    # Mark schemas
    EpigeneticMarkTypeResponse,
    MarkRelationshipResponse,
    # Experiment schemas
    ChIPSeqExperimentCreate,
    ChIPSeqExperimentResponse,
    ChIPSeqExperimentListResponse,
    # Peak schemas
    ChIPSeqPeak,
    ChIPSeqPeakCompact,
    ChIPSeqPaginatedResponse,
    # Gene-peak schemas
    GeneChIPSeqResponse,
    GeneChIPSeqSummary,
    GenePeakAssociation,
    MarkSummaryStats,
    # Comparison schemas
    ChIPSeqComparisonResponse,
    MarkComparisonEntry,
    PeakWidthPercentiles,
    OverlapRegion,
    OverlapStatistics,
    # Stats schemas
    ChIPSeqMarkStats,
    ChIPSeqGlobalStats,
    AvailableMarksResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features/chipseq", tags=["chipseq"])

# Default flanking region for gene queries (10kb)
DEFAULT_FLANKING_REGION = 10000


# =============================================================================
# Helper Functions
# =============================================================================

def get_chipseq_track_id(db: Session) -> int:
    """Get the track_id for ChIP-seq epigenetic track"""
    result = db.execute(
        text("SELECT track_id FROM feature_tracks WHERE track_name = 'chipseq_epigenetic'")
    ).fetchone()
    if not result:
        raise HTTPException(
            status_code=404,
            detail="ChIP-seq track not found. Please ensure the database schema is initialized."
        )
    return result[0]


def get_mark_type_id(db: Session, mark_name: str) -> int:
    """Get mark_type_id by mark name"""
    result = db.execute(
        text("SELECT mark_type_id FROM epigenetic_mark_types WHERE mark_name = :name"),
        {"name": mark_name}
    ).fetchone()
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Mark type not found: {mark_name}"
        )
    return result[0]


def parse_mark_types(mark_type_param: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated mark types into a list"""
    if not mark_type_param:
        return None
    return [m.strip() for m in mark_type_param.split(",") if m.strip()]


# =============================================================================
# Mark Types Endpoints
# =============================================================================

@router.get("/marks", response_model=List[EpigeneticMarkTypeResponse])
def list_mark_types(
    category: Optional[str] = Query(None, description="Filter by mark category"),
    active_only: bool = Query(True, description="Only return active marks"),
    db: Session = Depends(get_db),
):
    """
    List all available epigenetic mark types

    Returns the complete list of supported histone modifications with their
    properties, colors, and biological functions.
    """
    query = text("""
        SELECT
            mark_type_id,
            mark_name,
            mark_category,
            display_name,
            display_color,
            description,
            biological_function,
            associated_state,
            typical_signal_range,
            is_active,
            sort_order
        FROM epigenetic_mark_types
        WHERE (:category IS NULL OR mark_category = :category)
          AND (:active_only = FALSE OR is_active = TRUE)
        ORDER BY sort_order, mark_name
    """)

    rows = db.execute(query, {"category": category, "active_only": active_only}).fetchall()

    return [
        EpigeneticMarkTypeResponse(
            mark_type_id=row[0],
            mark_name=row[1],
            mark_category=row[2],
            display_name=row[3],
            display_color=row[4],
            description=row[5],
            biological_function=row[6],
            associated_state=row[7],
            typical_signal_range=row[8],
            is_active=row[9],
            sort_order=row[10],
        )
        for row in rows
    ]


@router.get("/marks/{species_id}", response_model=AvailableMarksResponse)
def get_available_marks_for_species(
    species_id: int,
    db: Session = Depends(get_db),
):
    """
    Get list of marks that have data available for a specific species

    Returns marks with at least one experiment/peak for the species.
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    # Query marks with experiments for this species
    query = text("""
        SELECT DISTINCT
            m.mark_type_id,
            m.mark_name,
            m.mark_category,
            m.display_name,
            m.display_color,
            m.description,
            m.biological_function,
            m.associated_state,
            m.typical_signal_range,
            m.is_active,
            m.sort_order,
            COUNT(DISTINCT e.experiment_id) as exp_count,
            COUNT(p.peak_id) as peak_count
        FROM epigenetic_mark_types m
        JOIN chipseq_experiments e ON m.mark_type_id = e.mark_type_id
        LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
        WHERE e.species_id = :species_id
          AND e.is_active = TRUE
          AND m.is_active = TRUE
        GROUP BY m.mark_type_id
        HAVING COUNT(DISTINCT e.experiment_id) > 0
        ORDER BY m.sort_order, m.mark_name
    """)

    rows = db.execute(query, {"species_id": species_id}).fetchall()

    marks = []
    total_experiments = 0
    total_peaks = 0

    for row in rows:
        marks.append(EpigeneticMarkTypeResponse(
            mark_type_id=row[0],
            mark_name=row[1],
            mark_category=row[2],
            display_name=row[3],
            display_color=row[4],
            description=row[5],
            biological_function=row[6],
            associated_state=row[7],
            typical_signal_range=row[8],
            is_active=row[9],
            sort_order=row[10],
        ))
        total_experiments += row[11]
        total_peaks += row[12] or 0

    return AvailableMarksResponse(
        species_id=species_id,
        species_code=species.species_code,
        marks=marks,
        total_experiments=total_experiments,
        total_peaks=total_peaks,
    )


@router.get("/marks/relationships", response_model=List[MarkRelationshipResponse])
def get_mark_relationships(
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    db: Session = Depends(get_db),
):
    """
    Get relationships between epigenetic marks

    Returns pairs of marks that have biological relationships (bivalent, antagonistic, etc.)
    """
    query = text("""
        SELECT
            r.relationship_id,
            m1.mark_name as mark_1,
            m2.mark_name as mark_2,
            r.relationship_type,
            r.description,
            r.biological_significance
        FROM mark_relationships r
        JOIN epigenetic_mark_types m1 ON r.mark_type_id_1 = m1.mark_type_id
        JOIN epigenetic_mark_types m2 ON r.mark_type_id_2 = m2.mark_type_id
        WHERE :relationship_type IS NULL OR r.relationship_type = :relationship_type
        ORDER BY r.relationship_type, m1.mark_name
    """)

    rows = db.execute(query, {"relationship_type": relationship_type}).fetchall()

    return [
        MarkRelationshipResponse(
            relationship_id=row[0],
            mark_1=row[1],
            mark_2=row[2],
            relationship_type=row[3],
            description=row[4],
            biological_significance=row[5],
        )
        for row in rows
    ]


# =============================================================================
# Experiment Endpoints
# =============================================================================

@router.get("/experiments", response_model=ChIPSeqExperimentListResponse)
def list_experiments(
    species_id: Optional[int] = Query(None, description="Filter by species"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s), comma-separated"),
    mark_category: Optional[str] = Query(None, description="Filter by mark category"),
    cell_type: Optional[str] = Query(None, description="Filter by cell type"),
    source_database: Optional[str] = Query(None, description="Filter by source (ENCODE, GEO)"),
    active_only: bool = Query(True, description="Only return active experiments"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    List ChIP-seq experiments with filtering options

    Supports filtering by species, mark type, cell type, and data source.
    """
    mark_types = parse_mark_types(mark_type)

    # Build query
    query = text("""
        WITH experiment_counts AS (
            SELECT experiment_id, COUNT(*) as peak_count
            FROM chipseq_peaks
            GROUP BY experiment_id
        )
        SELECT
            e.experiment_id,
            e.experiment_name,
            e.species_id,
            s.species_code,
            m.mark_name,
            m.mark_category,
            m.display_color,
            e.cell_type,
            e.tissue_type,
            e.cell_line,
            e.treatment,
            e.source_database,
            e.source_accession,
            e.peak_caller,
            e.reference_genome,
            e.total_reads,
            e.mapped_reads,
            e.frip_score,
            e.is_active,
            e.created_at,
            COALESCE(ec.peak_count, 0) as peak_count,
            COUNT(*) OVER() as total_count
        FROM chipseq_experiments e
        JOIN species s ON e.species_id = s.species_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        LEFT JOIN experiment_counts ec ON e.experiment_id = ec.experiment_id
        WHERE (:species_id IS NULL OR e.species_id = :species_id)
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:mark_category IS NULL OR m.mark_category = :mark_category)
          AND (:cell_type IS NULL OR e.cell_type ILIKE '%' || :cell_type || '%')
          AND (:source_database IS NULL OR e.source_database = :source_database)
          AND (:active_only = FALSE OR e.is_active = TRUE)
        ORDER BY e.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    offset = (page - 1) * page_size
    rows = db.execute(query, {
        "species_id": species_id,
        "mark_types": mark_types,
        "mark_category": mark_category,
        "cell_type": cell_type,
        "source_database": source_database,
        "active_only": active_only,
        "limit": page_size,
        "offset": offset,
    }).fetchall()

    if not rows:
        return ChIPSeqExperimentListResponse(total=0, items=[], page=page, page_size=page_size)

    total = rows[0][21] if rows else 0

    items = [
        ChIPSeqExperimentResponse(
            experiment_id=row[0],
            experiment_name=row[1],
            species_id=row[2],
            species_code=row[3],
            mark_type=row[4],
            mark_category=row[5],
            mark_display_color=row[6],
            cell_type=row[7],
            tissue_type=row[8],
            cell_line=row[9],
            treatment=row[10],
            source_database=row[11],
            source_accession=row[12],
            peak_caller=row[13],
            reference_genome=row[14],
            total_reads=row[15],
            mapped_reads=row[16],
            frip_score=float(row[17]) if row[17] else None,
            is_active=row[18],
            created_at=row[19],
            peak_count=row[20],
        )
        for row in rows
    ]

    return ChIPSeqExperimentListResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )


@router.get("/experiments/{experiment_id}", response_model=ChIPSeqExperimentResponse)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    """
    Get details for a specific ChIP-seq experiment
    """
    query = text("""
        WITH experiment_counts AS (
            SELECT experiment_id, COUNT(*) as peak_count
            FROM chipseq_peaks
            WHERE experiment_id = :experiment_id
            GROUP BY experiment_id
        )
        SELECT
            e.experiment_id,
            e.experiment_name,
            e.species_id,
            s.species_code,
            m.mark_name,
            m.mark_category,
            m.display_color,
            e.cell_type,
            e.tissue_type,
            e.cell_line,
            e.treatment,
            e.source_database,
            e.source_accession,
            e.peak_caller,
            e.reference_genome,
            e.total_reads,
            e.mapped_reads,
            e.frip_score,
            e.is_active,
            e.created_at,
            COALESCE(ec.peak_count, 0) as peak_count
        FROM chipseq_experiments e
        JOIN species s ON e.species_id = s.species_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        LEFT JOIN experiment_counts ec ON e.experiment_id = ec.experiment_id
        WHERE e.experiment_id = :experiment_id
    """)

    row = db.execute(query, {"experiment_id": experiment_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return ChIPSeqExperimentResponse(
        experiment_id=row[0],
        experiment_name=row[1],
        species_id=row[2],
        species_code=row[3],
        mark_type=row[4],
        mark_category=row[5],
        mark_display_color=row[6],
        cell_type=row[7],
        tissue_type=row[8],
        cell_line=row[9],
        treatment=row[10],
        source_database=row[11],
        source_accession=row[12],
        peak_caller=row[13],
        reference_genome=row[14],
        total_reads=row[15],
        mapped_reads=row[16],
        frip_score=float(row[17]) if row[17] else None,
        is_active=row[18],
        created_at=row[19],
        peak_count=row[20],
    )


# =============================================================================
# Gene-Level ChIP-seq Endpoints (Primary Use Case)
# =============================================================================

@router.get("/genes/{gene_id}", response_model=GeneChIPSeqResponse)
def get_gene_chipseq(
    gene_id: int,
    mark_type: Optional[str] = Query(
        None,
        description="Filter by mark type(s), comma-separated (e.g., H3K27me3,H3K4me3)"
    ),
    mark_category: Optional[str] = Query(None, description="Filter by mark category"),
    experiment_id: Optional[int] = Query(None, description="Filter by specific experiment"),
    min_fold_enrichment: Optional[float] = Query(
        None,
        ge=0,
        description="Minimum fold enrichment threshold"
    ),
    max_qvalue: Optional[float] = Query(
        0.05,
        ge=0,
        le=1,
        description="Maximum q-value threshold (default: 0.05)"
    ),
    flanking: int = Query(
        DEFAULT_FLANKING_REGION,
        ge=0,
        le=100000,
        description="Flanking region size in bp"
    ),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq peaks for a gene region

    Returns all peaks overlapping with the gene region (+/- flanking).
    Results are grouped by mark type.

    **Key Parameters:**
    - `mark_type`: Filter by one or more mark types (comma-separated)
    - `flanking`: Extend query region on each side (default: 10kb)
    - `max_qvalue`: Only return significant peaks (default: q < 0.05)

    **Example:**
    ```
    GET /features/chipseq/genes/12345?mark_type=H3K27me3,H3K4me3&flanking=20000
    ```
    """
    # 1. Query gene information
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # 2. Calculate query region
    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking
    tss = gene.gene_start if gene.strand == '+' else gene.gene_end

    # 3. Parse mark types
    mark_types = parse_mark_types(mark_type)

    # 4. Build and execute query
    query = text("""
        SELECT
            p.peak_id,
            p.experiment_id,
            m.mark_name,
            m.mark_category,
            m.display_color,
            p.chromosome,
            p.peak_start,
            p.peak_end,
            p.summit_position,
            p.fold_enrichment,
            p.qvalue,
            p.peak_width,
            CASE
                WHEN :strand = '+' THEN COALESCE(p.summit_position, (p.peak_start + p.peak_end) / 2) - :tss
                ELSE :tss - COALESCE(p.summit_position, (p.peak_start + p.peak_end) / 2)
            END as distance_to_tss,
            CASE
                WHEN p.peak_start <= :gene_start AND p.peak_end >= :gene_end THEN 'overlapping'
                WHEN p.peak_start >= :gene_start AND p.peak_end <= :gene_end THEN 'gene_body'
                WHEN p.peak_end <= :gene_start THEN
                    CASE WHEN :strand = '+' THEN 'upstream' ELSE 'downstream' END
                WHEN p.peak_start >= :gene_end THEN
                    CASE WHEN :strand = '+' THEN 'downstream' ELSE 'upstream' END
                WHEN ABS(COALESCE(p.summit_position, (p.peak_start + p.peak_end) / 2) - :tss) <= 2000 THEN 'promoter'
                ELSE 'gene_body'
            END as overlap_type,
            GREATEST(0, LEAST(p.peak_end, :region_end) - GREATEST(p.peak_start, :region_start)) as overlap_bp
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:mark_category IS NULL OR m.mark_category = :mark_category)
          AND (:experiment_id IS NULL OR e.experiment_id = :experiment_id)
          AND (:min_fold_enrichment IS NULL OR p.fold_enrichment >= :min_fold_enrichment)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
        ORDER BY m.sort_order, m.mark_name, p.fold_enrichment DESC
    """)

    rows = db.execute(query, {
        "species_id": gene.species_id,
        "chromosome": gene.chromosome,
        "region_start": region_start,
        "region_end": region_end,
        "gene_start": gene.gene_start,
        "gene_end": gene.gene_end,
        "tss": tss,
        "strand": gene.strand or '+',
        "mark_types": mark_types,
        "mark_category": mark_category,
        "experiment_id": experiment_id,
        "min_fold_enrichment": min_fold_enrichment,
        "max_qvalue": max_qvalue,
    }).fetchall()

    # 5. Group by mark type
    marks_dict = {}
    for row in rows:
        mark_name = row[2]
        if mark_name not in marks_dict:
            marks_dict[mark_name] = []

        marks_dict[mark_name].append(GenePeakAssociation(
            peak_id=row[0],
            chromosome=row[5],
            peak_start=row[6],
            peak_end=row[7],
            summit_position=row[8],
            fold_enrichment=float(row[9]) if row[9] else None,
            qvalue=float(row[10]) if row[10] else None,
            distance_to_tss=row[12],
            overlap_type=row[13],
            overlap_bp=row[14],
            mark_type=row[2],
            mark_category=row[3],
            experiment_id=row[1],
        ))

    return GeneChIPSeqResponse(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        gene_start=gene.gene_start,
        gene_end=gene.gene_end,
        strand=gene.strand or '.',
        region_start=region_start,
        region_end=region_end,
        marks=marks_dict,
        total_peaks=len(rows),
        marks_present=list(marks_dict.keys()),
    )


@router.get("/genes/{gene_id}/summary", response_model=GeneChIPSeqSummary)
def get_gene_chipseq_summary(
    gene_id: int,
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq summary statistics for a gene

    Returns aggregated statistics for all mark types with peaks in the gene region.
    Includes bivalent domain detection.
    """
    # 1. Query gene
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking
    region_length = region_end - region_start

    # 2. Query summary stats per mark
    query = text("""
        SELECT
            m.mark_name,
            m.mark_category,
            COUNT(*) as peak_count,
            MAX(p.fold_enrichment) as max_fold_enrichment,
            AVG(p.fold_enrichment) as avg_fold_enrichment,
            MIN(p.qvalue) as best_qvalue,
            SUM(GREATEST(0, LEAST(p.peak_end, :region_end) - GREATEST(p.peak_start, :region_start))) as coverage_bp,
            array_agg(DISTINCT
                CASE
                    WHEN p.peak_start >= :gene_start AND p.peak_end <= :gene_end THEN 'gene_body'
                    WHEN ABS(COALESCE(p.summit_position, (p.peak_start + p.peak_end) / 2) -
                         CASE WHEN :strand = '+' THEN :gene_start ELSE :gene_end END) <= 2000 THEN 'promoter'
                    ELSE 'flanking'
                END
            ) as overlap_types
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
        GROUP BY m.mark_name, m.mark_category
        ORDER BY m.mark_category, m.mark_name
    """)

    rows = db.execute(query, {
        "species_id": gene.species_id,
        "chromosome": gene.chromosome,
        "region_start": region_start,
        "region_end": region_end,
        "gene_start": gene.gene_start,
        "gene_end": gene.gene_end,
        "strand": gene.strand or '+',
        "max_qvalue": max_qvalue,
    }).fetchall()

    # 3. Build summary
    mark_summaries = []
    mark_names = set()
    total_peaks = 0

    for row in rows:
        mark_names.add(row[0])
        total_peaks += row[2]
        mark_summaries.append(MarkSummaryStats(
            mark_type=row[0],
            mark_category=row[1],
            peak_count=row[2],
            max_fold_enrichment=float(row[3]) if row[3] else None,
            avg_fold_enrichment=float(row[4]) if row[4] else None,
            best_qvalue=float(row[5]) if row[5] else None,
            total_peak_coverage_bp=int(row[6]) if row[6] else 0,
            overlap_types=row[7] if row[7] else [],
        ))

    # 4. Check for bivalent domain
    has_bivalent = 'H3K4me3' in mark_names and 'H3K27me3' in mark_names

    return GeneChIPSeqSummary(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        gene_start=gene.gene_start,
        gene_end=gene.gene_end,
        region_start=region_start,
        region_end=region_end,
        region_length=region_length,
        mark_summaries=mark_summaries,
        total_marks=len(mark_names),
        total_peaks=total_peaks,
        has_bivalent_domain=has_bivalent,
    )


# =============================================================================
# Helper Functions for Comparison Statistics (Phase 2.5)
# =============================================================================

def calculate_percentiles(values: List[float], percentiles: List[float]) -> Dict[str, float]:
    """Calculate percentiles for a list of values"""
    if not values:
        return {f"p{int(p*100)}": None for p in percentiles}

    sorted_values = sorted(values)
    n = len(sorted_values)
    result = {}

    for p in percentiles:
        key = f"p{int(p*100)}"
        if n == 1:
            result[key] = sorted_values[0]
        else:
            idx = p * (n - 1)
            lower_idx = int(idx)
            upper_idx = min(lower_idx + 1, n - 1)
            weight = idx - lower_idx
            result[key] = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

    return result


def find_pairwise_overlaps(
    peaks_1: List[Dict],
    peaks_2: List[Dict],
    mark_1: str,
    mark_2: str,
    chromosome: str,
) -> List[OverlapRegion]:
    """
    Find overlapping regions between two sets of peaks.
    Uses a simple interval intersection algorithm.
    """
    overlaps = []

    # Sort peaks by start position for efficiency
    sorted_peaks_1 = sorted(peaks_1, key=lambda p: p["peak_start"])
    sorted_peaks_2 = sorted(peaks_2, key=lambda p: p["peak_start"])

    # Determine overlap type based on mark pair
    is_bivalent = (
        (mark_1 == "H3K4me3" and mark_2 == "H3K27me3") or
        (mark_1 == "H3K27me3" and mark_2 == "H3K4me3")
    )
    overlap_type = "bivalent" if is_bivalent else None

    for p1 in sorted_peaks_1:
        for p2 in sorted_peaks_2:
            # Early termination: if p2 starts after p1 ends, no more overlaps possible
            if p2["peak_start"] >= p1["peak_end"]:
                break

            # Check overlap
            if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
                overlap_start = max(p1["peak_start"], p2["peak_start"])
                overlap_end = min(p1["peak_end"], p2["peak_end"])

                overlaps.append(OverlapRegion(
                    chromosome=chromosome,
                    start=overlap_start,
                    end=overlap_end,
                    length=overlap_end - overlap_start,
                    mark_1=mark_1,
                    mark_2=mark_2,
                    mark_1_peak_id=p1["peak_id"],
                    mark_2_peak_id=p2["peak_id"],
                    overlap_type=overlap_type,
                ))

    return overlaps


def compute_mark_statistics(peaks: List[Dict], region_start: int, region_end: int) -> Dict[str, Any]:
    """
    Compute enhanced statistics for a mark's peaks.

    Returns:
        Dictionary with avg, median, std of fold_enrichment,
        total_coverage_bp, and peak_width_percentiles.
    """
    if not peaks:
        return {
            "avg_fold_enrichment": None,
            "median_fold_enrichment": None,
            "std_fold_enrichment": None,
            "total_coverage_bp": 0,
            "peak_width_percentiles": None,
        }

    # Fold enrichment statistics
    fe_values = [p["fold_enrichment"] for p in peaks if p["fold_enrichment"] is not None]
    avg_fe = statistics.mean(fe_values) if fe_values else None
    median_fe = statistics.median(fe_values) if fe_values else None
    std_fe = statistics.stdev(fe_values) if len(fe_values) > 1 else None

    # Total coverage (accounting for potential overlaps between peaks of same mark)
    # Use interval merging to avoid double-counting
    intervals = sorted([(p["peak_start"], p["peak_end"]) for p in peaks])
    merged = []
    for start, end in intervals:
        # Clip to region boundaries
        start = max(start, region_start)
        end = min(end, region_end)
        if start >= end:
            continue

        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    total_coverage_bp = sum(end - start for start, end in merged)

    # Peak width percentiles
    peak_widths = [p["peak_end"] - p["peak_start"] for p in peaks]
    width_percentiles = calculate_percentiles(peak_widths, [0.25, 0.50, 0.75])

    return {
        "avg_fold_enrichment": avg_fe,
        "median_fold_enrichment": median_fe,
        "std_fold_enrichment": std_fe,
        "total_coverage_bp": total_coverage_bp,
        "peak_width_percentiles": PeakWidthPercentiles(
            p25=width_percentiles.get("p25"),
            p50=width_percentiles.get("p50"),
            p75=width_percentiles.get("p75"),
        ),
    }


# =============================================================================
# Multi-Mark Comparison Endpoint (Enhanced Phase 2.5)
# =============================================================================

@router.get("/genes/{gene_id}/compare", response_model=ChIPSeqComparisonResponse)
def compare_gene_marks(
    gene_id: int,
    marks: str = Query(
        ...,
        description="Comma-separated list of marks to compare (e.g., H3K27me3,H3K4me3)"
    ),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    include_all_overlaps: bool = Query(
        True,
        description="Include all pairwise overlaps (not just bivalent)"
    ),
    db: Session = Depends(get_db),
):
    """
    Compare multiple ChIP-seq marks for a gene (Enhanced Phase 2.5)

    Returns peaks for each specified mark with enhanced statistics:
    - median_fold_enrichment, std_fold_enrichment
    - total_coverage_bp (total base pairs covered)
    - peak_width_percentiles (p25, p50, p75)

    Also includes generalized overlap detection for any mark pair,
    not just H3K4me3 + H3K27me3 bivalent domains.

    **Example:**
    ```
    GET /features/chipseq/genes/12345/compare?marks=H3K27me3,H3K4me3,H3K27ac
    ```

    **New in Phase 2.5:**
    - Enhanced statistics per mark
    - Generalized pairwise overlap detection
    - Overlap statistics summary
    """
    # 1. Parse marks
    mark_list = [m.strip() for m in marks.split(",") if m.strip()]
    if len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 marks are required for comparison"
        )

    # 2. Query gene
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # 3. Query peaks for each mark with peak_width
    query = text("""
        SELECT
            p.peak_id,
            m.mark_name,
            m.mark_category,
            m.display_color,
            p.chromosome,
            p.peak_start,
            p.peak_end,
            p.summit_position,
            p.fold_enrichment,
            p.qvalue,
            COALESCE(p.peak_width, p.peak_end - p.peak_start) as peak_width
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
        ORDER BY m.mark_name, p.peak_start
    """)

    rows = db.execute(query, {
        "species_id": gene.species_id,
        "chromosome": gene.chromosome,
        "region_start": region_start,
        "region_end": region_end,
        "mark_list": mark_list,
        "max_qvalue": max_qvalue,
    }).fetchall()

    # 4. Group by mark
    marks_data: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        mark_name = row[1]
        if mark_name not in marks_data:
            marks_data[mark_name] = {
                "mark_category": row[2],
                "display_color": row[3],
                "peaks": [],
            }

        marks_data[mark_name]["peaks"].append({
            "peak_id": row[0],
            "chromosome": row[4],
            "peak_start": row[5],
            "peak_end": row[6],
            "summit": row[7],
            "fold_enrichment": float(row[8]) if row[8] else None,
            "qvalue": float(row[9]) if row[9] else None,
            "mark_type": mark_name,
            "peak_width": row[10],
        })

    # 5. Build comparison entries with enhanced statistics
    mark_entries = []
    for mark_name, data in marks_data.items():
        peaks = data["peaks"]

        # Compute enhanced statistics
        stats = compute_mark_statistics(peaks, region_start, region_end)

        mark_entries.append(MarkComparisonEntry(
            mark_type=mark_name,
            mark_category=data["mark_category"],
            display_color=data["display_color"],
            peaks=[ChIPSeqPeakCompact(**{k: v for k, v in p.items() if k != "peak_width"}) for p in peaks],
            peak_count=len(peaks),
            avg_fold_enrichment=stats["avg_fold_enrichment"],
            median_fold_enrichment=stats["median_fold_enrichment"],
            std_fold_enrichment=stats["std_fold_enrichment"],
            total_coverage_bp=stats["total_coverage_bp"],
            peak_width_percentiles=stats["peak_width_percentiles"],
        ))

    # 6. Find all pairwise overlapping regions (generalized algorithm)
    all_overlaps: List[OverlapRegion] = []
    overlap_stats: List[OverlapStatistics] = []
    bivalent_regions: List[Dict[str, Any]] = []

    mark_names = list(marks_data.keys())

    if include_all_overlaps and len(mark_names) >= 2:
        for mark_1, mark_2 in combinations(mark_names, 2):
            overlaps = find_pairwise_overlaps(
                marks_data[mark_1]["peaks"],
                marks_data[mark_2]["peaks"],
                mark_1,
                mark_2,
                gene.chromosome,
            )

            all_overlaps.extend(overlaps)

            # Compute overlap statistics for this pair
            if overlaps:
                total_bp = sum(o.length for o in overlaps)
                is_bivalent = (
                    (mark_1 == "H3K4me3" and mark_2 == "H3K27me3") or
                    (mark_1 == "H3K27me3" and mark_2 == "H3K4me3")
                )

                overlap_stats.append(OverlapStatistics(
                    mark_pair=f"{mark_1}:{mark_2}",
                    overlap_count=len(overlaps),
                    total_overlap_bp=total_bp,
                    avg_overlap_length=total_bp / len(overlaps),
                    is_bivalent=is_bivalent,
                ))

                # Build legacy bivalent_regions for backward compatibility
                if is_bivalent:
                    for o in overlaps:
                        bivalent_regions.append({
                            "chromosome": o.chromosome,
                            "start": o.start,
                            "end": o.end,
                            "length": o.length,
                            "h3k4me3_peak_id": o.mark_1_peak_id if o.mark_1 == "H3K4me3" else o.mark_2_peak_id,
                            "h3k27me3_peak_id": o.mark_1_peak_id if o.mark_1 == "H3K27me3" else o.mark_2_peak_id,
                        })

    return ChIPSeqComparisonResponse(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        region_start=region_start,
        region_end=region_end,
        marks=mark_entries,
        all_overlaps=all_overlaps if all_overlaps else None,
        overlap_statistics=overlap_stats if overlap_stats else None,
        overlapping_regions=None,  # Deprecated
        bivalent_regions=bivalent_regions if bivalent_regions else None,
    )


# =============================================================================
# Region-Based Queries
# =============================================================================

@router.get("/regions/{species_id}", response_model=ChIPSeqPaginatedResponse)
def get_peaks_by_region(
    species_id: int,
    chromosome: str = Query(..., description="Chromosome name"),
    start: int = Query(..., ge=0, description="Region start position"),
    end: int = Query(..., ge=0, description="Region end position"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s)"),
    min_fold_enrichment: Optional[float] = Query(None, ge=0),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq peaks for a specific genomic region

    Useful for browser-like views and custom region queries.
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    mark_types = parse_mark_types(mark_type)

    # Count query
    count_query = text("""
        SELECT COUNT(*)
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :end
          AND p.peak_end > :start
          AND e.is_active = TRUE
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:min_fold_enrichment IS NULL OR p.fold_enrichment >= :min_fold_enrichment)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
    """)

    total = db.execute(count_query, {
        "species_id": species_id,
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "mark_types": mark_types,
        "min_fold_enrichment": min_fold_enrichment,
        "max_qvalue": max_qvalue,
    }).scalar() or 0

    # Data query
    offset = (page - 1) * page_size
    data_query = text("""
        SELECT
            p.peak_id,
            p.experiment_id,
            m.mark_name,
            m.mark_category,
            p.chromosome,
            p.peak_start,
            p.peak_end,
            p.summit_position,
            p.peak_name,
            p.strand,
            p.fold_enrichment,
            p.log2_fold_enrichment,
            p.pvalue,
            p.neg_log10_pvalue,
            p.qvalue,
            p.neg_log10_qvalue,
            p.signal_value,
            p.score,
            p.peak_width
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :end
          AND p.peak_end > :start
          AND e.is_active = TRUE
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:min_fold_enrichment IS NULL OR p.fold_enrichment >= :min_fold_enrichment)
          AND (:max_qvalue IS NULL OR p.qvalue <= :max_qvalue)
        ORDER BY p.peak_start
        LIMIT :limit OFFSET :offset
    """)

    rows = db.execute(data_query, {
        "species_id": species_id,
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "mark_types": mark_types,
        "min_fold_enrichment": min_fold_enrichment,
        "max_qvalue": max_qvalue,
        "limit": page_size,
        "offset": offset,
    }).fetchall()

    items = [
        ChIPSeqPeak(
            peak_id=row[0],
            experiment_id=row[1],
            mark_type=row[2],
            mark_category=row[3],
            chromosome=row[4],
            peak_start=row[5],
            peak_end=row[6],
            summit_position=row[7],
            peak_name=row[8],
            strand=row[9] or ".",
            fold_enrichment=float(row[10]) if row[10] else None,
            log2_fold_enrichment=float(row[11]) if row[11] else None,
            pvalue=float(row[12]) if row[12] else None,
            neg_log10_pvalue=float(row[13]) if row[13] else None,
            qvalue=float(row[14]) if row[14] else None,
            neg_log10_qvalue=float(row[15]) if row[15] else None,
            signal_value=float(row[16]) if row[16] else None,
            score=row[17],
            peak_width=row[18] or (row[6] - row[5]),
        )
        for row in rows
    ]

    return ChIPSeqPaginatedResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Global Statistics
# =============================================================================

@router.get("/stats", response_model=ChIPSeqGlobalStats)
def get_global_stats(
    db: Session = Depends(get_db),
):
    """
    Get global ChIP-seq statistics

    Returns overall counts and per-mark statistics.
    Uses materialized view for fast response.
    """
    # Try materialized view first
    try:
        query = text("""
            SELECT
                species_code,
                mark_name,
                mark_category,
                display_color,
                experiment_count,
                total_peaks,
                avg_fold_enrichment,
                median_fold_enrichment,
                avg_peak_width
            FROM mv_chipseq_mark_stats
            ORDER BY species_code, mark_category, mark_name
        """)
        rows = db.execute(query).fetchall()

        if not rows:
            # Fallback to direct query if MV is empty
            raise Exception("Materialized view empty")

    except Exception:
        # Fallback to direct aggregation (slower)
        logger.warning("Using fallback query for ChIP-seq stats")
        query = text("""
            SELECT
                s.species_code,
                m.mark_name,
                m.mark_category,
                m.display_color,
                COUNT(DISTINCT e.experiment_id) as experiment_count,
                COUNT(p.peak_id) as total_peaks,
                AVG(p.fold_enrichment) as avg_fold_enrichment,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.fold_enrichment) as median_fold_enrichment,
                AVG(p.peak_width) as avg_peak_width
            FROM chipseq_experiments e
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            JOIN species s ON e.species_id = s.species_id
            LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
            WHERE e.is_active = TRUE
            GROUP BY s.species_code, m.mark_name, m.mark_category, m.display_color
            ORDER BY s.species_code, m.mark_category, m.mark_name
        """)
        rows = db.execute(query).fetchall()

    # Build response
    stats_by_mark = [
        ChIPSeqMarkStats(
            species_code=row[0],
            mark_name=row[1],
            mark_category=row[2],
            display_color=row[3],
            experiment_count=row[4],
            total_peaks=row[5] or 0,
            avg_fold_enrichment=float(row[6]) if row[6] else None,
            median_fold_enrichment=float(row[7]) if row[7] else None,
            avg_peak_width=float(row[8]) if row[8] else None,
        )
        for row in rows
    ]

    total_experiments = sum(s.experiment_count for s in stats_by_mark)
    total_peaks = sum(s.total_peaks for s in stats_by_mark)
    marks_available = list(set(s.mark_name for s in stats_by_mark))
    species_available = list(set(s.species_code for s in stats_by_mark))

    return ChIPSeqGlobalStats(
        total_experiments=total_experiments,
        total_peaks=total_peaks,
        marks_available=sorted(marks_available),
        species_available=sorted(species_available),
        stats_by_mark=stats_by_mark,
    )


# =============================================================================
# Export Endpoints (Phase 2.5)
# =============================================================================

@router.get("/genes/{gene_id}/compare/export")
def export_comparison(
    gene_id: int,
    marks: str = Query(
        ...,
        description="Comma-separated list of marks to compare"
    ),
    format: ExportFormat = Query(
        ExportFormat.csv,
        description="Export format (csv, tsv, json)"
    ),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    include_overlaps: bool = Query(True, description="Include overlap data"),
    db: Session = Depends(get_db),
):
    """
    Export comparison data in CSV, TSV, or JSON format (Phase 2.5)

    Downloads the comparison results for further analysis in external tools.

    **Example:**
    ```
    GET /features/chipseq/genes/12345/compare/export?marks=H3K27me3,H3K4me3&format=csv
    ```
    """
    # Get comparison data (reuse existing logic)
    mark_list = [m.strip() for m in marks.split(",") if m.strip()]
    if len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 marks are required for comparison"
        )

    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # Query peaks
    query = text("""
        SELECT
            p.peak_id,
            m.mark_name,
            m.mark_category,
            p.chromosome,
            p.peak_start,
            p.peak_end,
            p.summit_position,
            p.fold_enrichment,
            p.qvalue,
            COALESCE(p.peak_width, p.peak_end - p.peak_start) as peak_width
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
        ORDER BY m.mark_name, p.peak_start
    """)

    rows = db.execute(query, {
        "species_id": gene.species_id,
        "chromosome": gene.chromosome,
        "region_start": region_start,
        "region_end": region_end,
        "mark_list": mark_list,
        "max_qvalue": max_qvalue,
    }).fetchall()

    # Prepare data for export
    peaks_data = []
    marks_data = {}

    for row in rows:
        peak_dict = {
            "peak_id": row[0],
            "mark_type": row[1],
            "mark_category": row[2],
            "chromosome": row[3],
            "peak_start": row[4],
            "peak_end": row[5],
            "summit_position": row[6],
            "fold_enrichment": float(row[7]) if row[7] else None,
            "qvalue": float(row[8]) if row[8] else None,
            "peak_width": row[9],
        }
        peaks_data.append(peak_dict)

        mark_name = row[1]
        if mark_name not in marks_data:
            marks_data[mark_name] = []
        marks_data[mark_name].append(peak_dict)

    # Calculate overlaps if requested
    overlaps_data = []
    if include_overlaps and len(marks_data) >= 2:
        mark_names = list(marks_data.keys())
        for mark_1, mark_2 in combinations(mark_names, 2):
            for p1 in marks_data[mark_1]:
                for p2 in marks_data[mark_2]:
                    if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
                        overlap_start = max(p1["peak_start"], p2["peak_start"])
                        overlap_end = min(p1["peak_end"], p2["peak_end"])
                        overlaps_data.append({
                            "chromosome": gene.chromosome,
                            "start": overlap_start,
                            "end": overlap_end,
                            "length": overlap_end - overlap_start,
                            "mark_1": mark_1,
                            "mark_2": mark_2,
                            "mark_1_peak_id": p1["peak_id"],
                            "mark_2_peak_id": p2["peak_id"],
                        })

    # Generate output based on format
    if format == ExportFormat.json:
        import json
        output = json.dumps({
            "gene_id": gene_id,
            "gene_name": gene.gene_name,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "peaks": peaks_data,
            "overlaps": overlaps_data if include_overlaps else None,
        }, indent=2)
        media_type = "application/json"
        filename = f"chipseq_compare_{gene_id}.json"
    else:
        # CSV or TSV
        delimiter = "\t" if format == ExportFormat.tsv else ","
        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)

        # Write peaks header and data
        writer.writerow([
            "peak_id", "mark_type", "mark_category", "chromosome",
            "peak_start", "peak_end", "summit_position",
            "fold_enrichment", "qvalue", "peak_width"
        ])
        for peak in peaks_data:
            writer.writerow([
                peak["peak_id"], peak["mark_type"], peak["mark_category"],
                peak["chromosome"], peak["peak_start"], peak["peak_end"],
                peak["summit_position"], peak["fold_enrichment"],
                peak["qvalue"], peak["peak_width"]
            ])

        # Write overlaps section if requested
        if include_overlaps and overlaps_data:
            writer.writerow([])  # Empty row separator
            writer.writerow(["# Overlapping Regions"])
            writer.writerow([
                "chromosome", "start", "end", "length",
                "mark_1", "mark_2", "mark_1_peak_id", "mark_2_peak_id"
            ])
            for overlap in overlaps_data:
                writer.writerow([
                    overlap["chromosome"], overlap["start"], overlap["end"],
                    overlap["length"], overlap["mark_1"], overlap["mark_2"],
                    overlap["mark_1_peak_id"], overlap["mark_2_peak_id"]
                ])

        output = output.getvalue()
        media_type = "text/csv" if format == ExportFormat.csv else "text/tab-separated-values"
        ext = "csv" if format == ExportFormat.csv else "tsv"
        filename = f"chipseq_compare_{gene_id}.{ext}"

    return StreamingResponse(
        io.BytesIO(output.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/genes/{gene_id}/overlaps/export")
def export_overlaps_bed(
    gene_id: int,
    marks: str = Query(
        ...,
        description="Comma-separated list of marks to compare"
    ),
    format: ExportFormat = Query(
        ExportFormat.bed,
        description="Export format (bed, csv, tsv)"
    ),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    mark_pair: Optional[str] = Query(
        None,
        description="Filter by specific mark pair (e.g., 'H3K4me3:H3K27me3')"
    ),
    min_overlap_bp: int = Query(0, ge=0, description="Minimum overlap length"),
    db: Session = Depends(get_db),
):
    """
    Export overlap regions in BED format (Phase 2.5)

    Downloads overlapping regions for use in genome browsers or downstream analysis.
    BED format: chromosome, start, end, name, score, strand

    **Example:**
    ```
    GET /features/chipseq/genes/12345/overlaps/export?marks=H3K27me3,H3K4me3&format=bed
    ```
    """
    mark_list = [m.strip() for m in marks.split(",") if m.strip()]
    if len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 marks are required for overlap detection"
        )

    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # Query peaks
    query = text("""
        SELECT
            p.peak_id,
            m.mark_name,
            p.chromosome,
            p.peak_start,
            p.peak_end
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
        ORDER BY m.mark_name, p.peak_start
    """)

    rows = db.execute(query, {
        "species_id": gene.species_id,
        "chromosome": gene.chromosome,
        "region_start": region_start,
        "region_end": region_end,
        "mark_list": mark_list,
        "max_qvalue": max_qvalue,
    }).fetchall()

    # Group by mark
    marks_data = {}
    for row in rows:
        mark_name = row[1]
        if mark_name not in marks_data:
            marks_data[mark_name] = []
        marks_data[mark_name].append({
            "peak_id": row[0],
            "peak_start": row[3],
            "peak_end": row[4],
        })

    # Find overlaps
    overlaps = []
    mark_names = list(marks_data.keys())

    # Parse mark_pair filter if provided
    filter_marks = None
    if mark_pair:
        filter_marks = set(mark_pair.split(":"))

    for mark_1, mark_2 in combinations(mark_names, 2):
        # Apply mark pair filter
        if filter_marks and {mark_1, mark_2} != filter_marks:
            continue

        for p1 in marks_data[mark_1]:
            for p2 in marks_data[mark_2]:
                if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
                    overlap_start = max(p1["peak_start"], p2["peak_start"])
                    overlap_end = min(p1["peak_end"], p2["peak_end"])
                    overlap_length = overlap_end - overlap_start

                    if overlap_length >= min_overlap_bp:
                        overlaps.append({
                            "chromosome": gene.chromosome,
                            "start": overlap_start,
                            "end": overlap_end,
                            "name": f"{mark_1}_{mark_2}_overlap",
                            "score": min(1000, int(overlap_length)),  # BED score 0-1000
                            "strand": ".",
                            "mark_1": mark_1,
                            "mark_2": mark_2,
                            "length": overlap_length,
                        })

    # Sort by position
    overlaps.sort(key=lambda x: (x["chromosome"], x["start"]))

    # Generate output
    if format == ExportFormat.bed:
        output = io.StringIO()
        # BED header (optional track line)
        output.write(f"track name=\"ChIP-seq_Overlaps_{gene_id}\" description=\"Overlapping regions for gene {gene.gene_name}\"\n")
        for o in overlaps:
            output.write(f"{o['chromosome']}\t{o['start']}\t{o['end']}\t{o['name']}\t{o['score']}\t{o['strand']}\n")
        media_type = "text/plain"
        filename = f"chipseq_overlaps_{gene_id}.bed"
    elif format == ExportFormat.json:
        import json
        output = io.StringIO()
        output.write(json.dumps({
            "gene_id": gene_id,
            "gene_name": gene.gene_name,
            "overlaps": overlaps,
        }, indent=2))
        media_type = "application/json"
        filename = f"chipseq_overlaps_{gene_id}.json"
    else:
        # CSV or TSV
        delimiter = "\t" if format == ExportFormat.tsv else ","
        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        writer.writerow(["chromosome", "start", "end", "name", "length", "mark_1", "mark_2"])
        for o in overlaps:
            writer.writerow([
                o["chromosome"], o["start"], o["end"], o["name"],
                o["length"], o["mark_1"], o["mark_2"]
            ])
        media_type = "text/csv" if format == ExportFormat.csv else "text/tab-separated-values"
        ext = "csv" if format == ExportFormat.csv else "tsv"
        filename = f"chipseq_overlaps_{gene_id}.{ext}"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
