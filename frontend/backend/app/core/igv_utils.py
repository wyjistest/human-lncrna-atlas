"""
IGV utility functions
包含基因组参考查询、颜色配置等工具函数
"""
import os
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
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

    ref_data = dict(GENOME_REFERENCES[species_id])

    def genomes_file_exists(filename: str) -> bool:
        genomes_dir = settings.GENOMES_DIR
        if not genomes_dir:
            return False
        return os.path.exists(os.path.join(genomes_dir, filename))

    # hg19 离线化：当本地 2bit 存在时，优先使用 /genomes 静态文件服务，避免 IGV 内置 hg19 触发外网依赖。
    # 注意：保持向后兼容——若本地文件不存在，则继续使用内置 hg19（twoBitURL=None）。
    if species_id == 1:
        hg19_twobit = "hg19.2bit"
        if genomes_file_exists(hg19_twobit):
            ref_data["twoBitURL"] = f"/genomes/{hg19_twobit}"

            # 可选：染色体大小文件（若存在则提供，提升离线一致性）
            if genomes_file_exists("hg19.chrom.sizes"):
                ref_data["chromSizesURL"] = "/genomes/hg19.chrom.sizes"

            # 可选：cytoband（用于 ideogram，可缺省）
            if genomes_file_exists("cytoBand.hg19.txt.gz"):
                ref_data["cytobandURL"] = "/genomes/cytoBand.hg19.txt.gz"

            # 可选：染色体别名表（chrM/MT 等别名解析，可缺省）
            if genomes_file_exists("hg19_alias.tab"):
                ref_data["aliasURL"] = "/genomes/hg19_alias.tab"

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
