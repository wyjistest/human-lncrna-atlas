"""
ChIP-seq Epigenetic Marks API Router
Provides unified endpoints for multiple histone modifications

Phase 2.5 Enhancements:
- Redis caching for expensive comparison endpoints
- Rate limiting for API protection

主路由文件，保留全局配置并整合子路由
"""
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.cache import cache, cached
from app.core.database import get_db
from app.schemas.chipseq import ChIPSeqGlobalStats, ChIPSeqMarkStats
from app.routers.chipseq_rate_limit import (
    chipseq_limiter,
    rate_limit,
    DEFAULT_FLANKING_REGION,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features/chipseq", tags=["chipseq"])


# =============================================================================
# Import and Register Sub-routers
# NOTE: These imports are placed here (after rate_limit definition) to avoid
# circular imports.
# =============================================================================

from app.routers.chipseq_marks import router as marks_router  # noqa: E402
from app.routers.chipseq_experiments import router as experiments_router  # noqa: E402
from app.routers.chipseq_genes import router as genes_router  # noqa: E402
from app.routers.chipseq_regions import router as regions_router  # noqa: E402
from app.routers.chipseq_export import router as export_router  # noqa: E402

# Register all sub-routers
router.include_router(marks_router)
router.include_router(experiments_router)
router.include_router(genes_router)
router.include_router(regions_router)
router.include_router(export_router)


# =============================================================================
# Global Statistics Endpoint (kept in main router)
# =============================================================================

@router.get("/stats", response_model=ChIPSeqGlobalStats)
@rate_limit("30/minute")
@cached("chipseq:global_stats", ttl=cache.TTL_STATS)
def get_global_stats(
    request: Request,
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


# Export rate_limit and limiter for sub-routers
__all__ = ['router', 'rate_limit', 'chipseq_limiter', 'DEFAULT_FLANKING_REGION']
