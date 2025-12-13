"""
ChIP-seq Database Query Utilities
数据库查询辅助函数
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException


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
