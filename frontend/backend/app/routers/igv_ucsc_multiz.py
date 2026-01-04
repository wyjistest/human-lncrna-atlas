"""
IGV UCSC Multiz / Conservation 轨道配置

说明：
- UCSC 的 multiz 多序列比对（Multiple Alignment）本身通常以 .maf.gz 提供；
  但 IGV.js 目前支持的 “maf” 格式是 Mutation Annotation Format（突变注释），
  并不等同于 UCSC multiz 的 Multiple Alignment Format。
- 因此，这里提供的是基于 multiz 的衍生轨道（保守性分数，如 phastCons/phyloP），
  以 BigWig 形式加载，IGV.js 可直接通过 URL + HTTP Range 请求按需获取数据。

范围与约束：
- 本端点仅提供 multiz 衍生的保守性分数轨道（phastCons/phyloP），不提供 UCSC MAF 多序列比对本身。
- 轨道按 `species_id -> genome_assembly(reference.id)` 在 `GENOMES_DIR` 中“可发现”返回；缺文件时返回空列表（不报错）。
- 本端点只返回静态 track 配置，不代理数据；数据由后端静态文件服务 `/genomes` 提供。
- 使用前需设置 `GENOMES_DIR` 指向包含对应 `.bw` 文件的目录，并确保后端已挂载基因组文件服务。
"""

from __future__ import annotations

import logging
import os
from glob import glob

from fastapi import APIRouter, HTTPException, Path, Request

from app.config.igv_genomes import SPECIES_NAMES
from app.core.cache import cache
from app.core.config import settings
from app.core.utils import sanitize_for_log
from app.core.igv_utils import get_genome_reference
from app.routers.chipseq_rate_limit import rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)


def _find_best_bigwig(genomes_dir: str, patterns: list[str]) -> str | None:
    candidates: set[str] = set()
    for pattern in patterns:
        for path in glob(os.path.join(genomes_dir, pattern)):
            if os.path.isfile(path):
                candidates.add(os.path.basename(path))

    if not candidates:
        return None

    def score(name: str) -> tuple[int, int, str]:
        # 经验优先级：优先 100way，其次文件名更短（更接近标准命名），最后按字典序稳定排序
        return (0 if "100way" in name.lower() else 1, len(name), name)

    return sorted(candidates, key=score)[0]


def _build_multiz_conservation_tracks(genomes_dir: str, assembly: str) -> list[dict]:
    tracks: list[dict] = []

    phastcons = _find_best_bigwig(
        genomes_dir,
        [
            f"{assembly}.*phastCons*.bw",
            f"{assembly}*phastCons*.bw",
        ],
    )
    if phastcons:
        track_id = f"ucsc_multiz_phastCons_{assembly}"
        if assembly == "hg19" and phastcons == "hg19.100way.phastCons.bw":
            track_id = "ucsc_multiz_phastCons100way_hg19"

        tracks.append(
            {
                "id": track_id,
                "name": f"Multiz Conservation (phastCons, {assembly})",
                "type": "wig",
                "format": "bigwig",
                "url": f"/genomes/{phastcons}",
                # phastCons 取值范围通常为 [0, 1]，固定范围能显著提升可比性与可读性
                "min": 0,
                "max": 1,
                "color": "#1B5E20",
                "height": 80,
                "description": f"phastCons conservation scores derived from {assembly} multiz alignment (BigWig, local /genomes).",
            }
        )

    phylop = _find_best_bigwig(
        genomes_dir,
        [
            f"{assembly}.*phyloP*.bw",
            f"{assembly}*phyloP*.bw",
        ],
    )
    if phylop:
        track_id = f"ucsc_multiz_phyloP_{assembly}"
        if assembly == "hg19" and phylop == "hg19.100way.phyloP100way.bw":
            track_id = "ucsc_multiz_phyloP100way_hg19"

        tracks.append(
            {
                "id": track_id,
                "name": f"Multiz Conservation (phyloP, {assembly})",
                "type": "wig",
                "format": "bigwig",
                "url": f"/genomes/{phylop}",
                # phyloP 同时包含正/负分数；用 diverging 色阶更直观地凸显保守/加速演化信号
                "min": -2,
                "max": 2,
                "graphType": "heatmap",
                "colorScale": {
                    "type": "diverging",
                    "min": -2,
                    "mid": 0,
                    "max": 2,
                    "minColor": "rgb(46,56,183)",
                    "midColor": "white",
                    "maxColor": "rgb(164,0,30)",
                },
                "color": "#1565C0",
                "height": 80,
                "description": f"phyloP scores derived from {assembly} multiz alignment (BigWig, local /genomes).",
            }
        )

    return tracks


@router.get("/config/ucsc-multiz/{species_id}")
@rate_limit("60/minute")
def get_ucsc_multiz_track_configs(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)"),
):
    """
    获取 UCSC multiz 衍生轨道（保守性分数）IGV.js 配置

    该端点按本地 GENOMES_DIR 中的文件“可发现”返回保守性轨道：
    - 若对应 assembly 的 BigWig 文件不存在，则返回空列表（不会报错）。
    - 这样可以在不引入仓库大文件的前提下，允许用户按需安装其它物种/assembly 的保守性数据。
    """
    # 获取该物种的 assembly（与 IGV 主配置保持一致）
    try:
        reference = get_genome_reference(species_id)
    except HTTPException as e:
        raise HTTPException(status_code=404, detail=str(e.detail)) from e

    genomes_dir = settings.GENOMES_DIR
    dir_mtime: int | None = None
    if genomes_dir and os.path.exists(genomes_dir):
        try:
            dir_mtime = int(os.stat(genomes_dir).st_mtime)
        except OSError as e:
            logger.debug(
                "Failed to stat GENOMES_DIR=%s: %s",
                sanitize_for_log(genomes_dir),
                sanitize_for_log(e),
                exc_info=True,
            )
            dir_mtime = None

    cache_key = cache.make_key(
        "igv:ucsc_multiz_tracks",
        species_id=species_id,
        genome_assembly=reference.id,
        genomes_dir=genomes_dir or "",
        dir_mtime=dir_mtime,
    )
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    if not genomes_dir or not os.path.exists(genomes_dir):
        tracks: list[dict] = []
    else:
        tracks = _build_multiz_conservation_tracks(genomes_dir, reference.id)

    result = {
        "success": True,
        "data": {
            "tracks": tracks,
            "species_id": species_id,
            "species_name": SPECIES_NAMES.get(species_id, f"Species {species_id}"),
            "genome_assembly": reference.id,
        },
        "message": (
            f"UCSC multiz-derived conservation tracks for {reference.id}: "
            f"{', '.join([t['id'] for t in tracks]) if tracks else 'none'}"
        ),
    }

    cache.set(cache_key, result, cache.TTL_STATS)
    return result
