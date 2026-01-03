"""
IGV UCSC Multiz / Conservation 轨道配置

说明：
- UCSC 的 multiz 多序列比对（Multiple Alignment）本身通常以 .maf.gz 提供；
  但 IGV.js 目前支持的 “maf” 格式是 Mutation Annotation Format（突变注释），
  并不等同于 UCSC multiz 的 Multiple Alignment Format。
- 因此，这里提供的是基于 multiz 的衍生轨道（保守性分数，如 phastCons/phyloP），
  以 BigWig 形式加载，IGV.js 可直接通过 URL + HTTP Range 请求按需获取数据。

范围与约束：
- 当前项目人类参考基因组使用 hg19（见前端内置基因组配置），因此仅对 Human/species_id=1
  提供 hg19 的 UCSC 保守性轨道；其它物种/assembly 后续可按需扩展。
- 本端点只返回静态 track 配置，不代理数据；数据由后端静态文件服务 `/genomes` 提供。
- 使用前需设置 `GENOMES_DIR` 指向包含对应 `.bw` 文件的目录，并确保后端已挂载基因组文件服务。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Request

from app.routers.chipseq_rate_limit import rate_limit

router = APIRouter()


UCSC_HG19_MULTIZ_TRACKS = [
    {
        "id": "ucsc_multiz_phastCons100way_hg19",
        "name": "Multiz Conservation (phastCons 100-way, hg19)",
        "type": "wig",
        "format": "bigwig",
        "url": "/genomes/hg19.100way.phastCons.bw",
        "color": "#27AE60",
        "height": 60,
        "description": "phastCons conservation scores derived from hg19 multiz 100-way alignment (BigWig, local /genomes).",
    },
    {
        "id": "ucsc_multiz_phyloP100way_hg19",
        "name": "Multiz Conservation (phyloP 100-way, hg19)",
        "type": "wig",
        "format": "bigwig",
        "url": "/genomes/hg19.100way.phyloP100way.bw",
        "color": "#2980B9",
        "height": 60,
        "description": "phyloP scores derived from hg19 multiz 100-way alignment (BigWig, local /genomes).",
    },
]


@router.get("/config/ucsc-multiz/{species_id}")
@rate_limit("60/minute")
def get_ucsc_multiz_track_configs(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)"),
):
    """
    获取 UCSC multiz 衍生轨道（保守性分数）IGV.js 配置

    当前仅支持 Human/hg19（species_id=1），以避免 assembly 不一致导致坐标错位。
    """
    if species_id != 1:
        raise HTTPException(
            status_code=400,
            detail="UCSC multiz conservation tracks are currently only available for Human (species_id=1, hg19).",
        )

    return {
        "success": True,
        "data": {
            "tracks": UCSC_HG19_MULTIZ_TRACKS,
            "species_id": species_id,
            "species_name": "Human",
            "genome_assembly": "hg19",
        },
        "message": "UCSC multiz-derived conservation tracks (hg19, 100-way): phastCons + phyloP",
    }
