"""
ChIP-seq Epigenetic Marks API Router
Provides unified endpoints for multiple histone modifications
"""
import logging
from typing import Optional, List
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
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
          AND (:max_qvalue IS NULL OR p.qvalue <= :max_qvalue)
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
          AND (:max_qvalue IS NULL OR p.qvalue <= :max_qvalue)
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
# Multi-Mark Comparison Endpoint
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
    db: Session = Depends(get_db),
):
    """
    Compare multiple ChIP-seq marks for a gene

    Returns peaks for each specified mark and identifies overlapping regions.
    Useful for bivalent domain analysis and mark co-occurrence studies.

    **Example:**
    ```
    GET /features/chipseq/genes/12345/compare?marks=H3K27me3,H3K4me3,H3K27ac
    ```
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

    # 3. Query peaks for each mark
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
            p.qvalue
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND (:max_qvalue IS NULL OR p.qvalue <= :max_qvalue)
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
    marks_data = {}
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
        })

    # 5. Build comparison entries
    mark_entries = []
    for mark_name, data in marks_data.items():
        peaks = data["peaks"]
        avg_fe = None
        if peaks:
            fe_values = [p["fold_enrichment"] for p in peaks if p["fold_enrichment"]]
            if fe_values:
                avg_fe = sum(fe_values) / len(fe_values)

        mark_entries.append(MarkComparisonEntry(
            mark_type=mark_name,
            mark_category=data["mark_category"],
            display_color=data["display_color"],
            peaks=[ChIPSeqPeakCompact(**p) for p in peaks],
            peak_count=len(peaks),
            avg_fold_enrichment=avg_fe,
        ))

    # 6. Find overlapping regions (simplified interval intersection)
    overlapping_regions = []
    if "H3K4me3" in marks_data and "H3K27me3" in marks_data:
        # Simple bivalent detection: find overlapping peaks
        h3k4me3_peaks = marks_data["H3K4me3"]["peaks"]
        h3k27me3_peaks = marks_data["H3K27me3"]["peaks"]

        bivalent_regions = []
        for p1 in h3k4me3_peaks:
            for p2 in h3k27me3_peaks:
                # Check overlap
                if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
                    overlap_start = max(p1["peak_start"], p2["peak_start"])
                    overlap_end = min(p1["peak_end"], p2["peak_end"])
                    bivalent_regions.append({
                        "chromosome": gene.chromosome,
                        "start": overlap_start,
                        "end": overlap_end,
                        "length": overlap_end - overlap_start,
                        "h3k4me3_peak_id": p1["peak_id"],
                        "h3k27me3_peak_id": p2["peak_id"],
                    })
    else:
        bivalent_regions = None

    return ChIPSeqComparisonResponse(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        region_start=region_start,
        region_end=region_end,
        marks=mark_entries,
        overlapping_regions=overlapping_regions if overlapping_regions else None,
        bivalent_regions=bivalent_regions,
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
          AND (:max_qvalue IS NULL OR p.qvalue <= :max_qvalue)
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
