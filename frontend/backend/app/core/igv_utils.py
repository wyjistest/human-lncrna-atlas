"""
IGV utility functions
包含基因组参考查询、颜色配置等工具函数
"""
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config.igv_genomes import (
    GENOME_REFERENCES,
    CHIPSEQ_MARK_COLORS,
    DEFAULT_CHIPSEQ_COLOR,
)
from app.schemas.igv import GenomeReference
from app.models import FeatureTrack


def get_genome_reference(species_id: int) -> GenomeReference:
    """获取指定物种的基因组参考配置"""
    if species_id not in GENOME_REFERENCES:
        raise HTTPException(
            status_code=404,
            detail=f"Genome reference not found for species_id: {species_id}"
        )

    ref_data = GENOME_REFERENCES[species_id]
    return GenomeReference(**ref_data)


def get_chipseq_mark_color(mark_name: str, db_color: Optional[str] = None) -> str:
    """
    Get the display color for a ChIP-seq mark type.

    Priority:
    1. Database-defined color (from epigenetic_mark_types.display_color)
    2. Predefined color in CHIPSEQ_MARK_COLORS
    3. Default gray color

    Args:
        mark_name: The mark type name (e.g., H3K27me3)
        db_color: Color from database (if available)

    Returns:
        Hex color code (e.g., #9B59B6)
    """
    if db_color and db_color != '#666666':  # Skip default gray
        return db_color
    return CHIPSEQ_MARK_COLORS.get(mark_name, DEFAULT_CHIPSEQ_COLOR)


def get_repeatmasker_track_id(db: Session) -> Optional[int]:
    """
    Get the track_id for RepeatMasker annotations.

    Returns:
        track_id if RepeatMasker track exists, None otherwise
    """
    track = db.query(FeatureTrack).filter(
        FeatureTrack.track_name == 'repeatmasker_repeats'
    ).first()
    return track.track_id if track else None
