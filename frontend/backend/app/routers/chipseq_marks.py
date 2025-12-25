"""
ChIP-seq Mark Types API Router
管理表观遗传标记类型的端点
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.models import Species
from app.schemas.chipseq import (
    EpigeneticMarkTypeResponse,
    MarkRelationshipResponse,
    AvailableMarksResponse,
)

router = APIRouter()


@router.get("/marks", response_model=List[EpigeneticMarkTypeResponse])
@rate_limit("30/minute")
def list_mark_types(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by mark category"),
    active_only: bool = Query(True, description="Only return active marks"),
    db: Session = Depends(get_db),
):
    """
    List all available epigenetic mark types

    Returns the complete list of supported histone modifications with their
    properties, colors, and biological functions.
    """
    where_clauses = []
    params = {}
    if category is not None:
        where_clauses.append("mark_category = :category")
        params["category"] = category
    if active_only:
        where_clauses.append("is_active = TRUE")
    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    query = text(
        f"""
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
        WHERE {where_sql}
        ORDER BY sort_order, mark_name
        """  # noqa: S608
    )

    rows = db.execute(query, params).fetchall()

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


# NOTE: /marks/relationships must be defined BEFORE /marks/{species_id} to avoid routing conflict
@router.get("/marks/relationships", response_model=List[MarkRelationshipResponse])
@rate_limit("30/minute")
def get_mark_relationships(
    request: Request,
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    db: Session = Depends(get_db),
):
    """
    Get relationships between epigenetic marks

    Returns pairs of marks that have biological relationships (bivalent, antagonistic, etc.)
    """
    where_sql = "r.relationship_type = :relationship_type" if relationship_type is not None else "TRUE"

    query = text(
        f"""
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
        WHERE {where_sql}
        ORDER BY r.relationship_type, m1.mark_name
        """  # noqa: S608
    )

    params = {"relationship_type": relationship_type} if relationship_type is not None else {}
    rows = db.execute(query, params).fetchall()

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


@router.get("/marks/{species_id}", response_model=AvailableMarksResponse)
@rate_limit("30/minute")
def get_available_marks_for_species(
    request: Request,
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
