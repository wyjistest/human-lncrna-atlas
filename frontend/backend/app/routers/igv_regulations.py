"""
IGV调控轨道路由
提供调控关系的BED和BEDPE格式数据导出
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.utils import sanitize_for_log
from app.routers.chipseq_rate_limit import rate_limit
from app.models import Species
from app.core.igv_stream_generators import generate_bed_stream, generate_bedpe_stream
from app.utils.http_headers import content_disposition_attachment

logger = logging.getLogger(__name__)

router = APIRouter()

# 10Mb 以内允许 IGV 区域查询，避免一次请求拖垮数据库/连接池
MAX_REGION_SIZE_BP = 10_000_000

# 无区域过滤（chr/start/end 均缺失）且无 lncrna 过滤时的默认返回上限：防止全表流式导出导致 DoS
DEFAULT_MAX_RECORDS_NO_REGION = 50_000
MAX_LIMIT = 100_000


@router.get("/tracks/regulations/{species_id}.bed")
@rate_limit("60/minute")
def get_regulations_bed(
    request: Request,
    species_id: int,
    chr: Optional[str] = Query(None, max_length=64, description="染色体过滤，如 chr1"),
    # IGV.js webservice 轨道会传递浮点坐标（像素换算），这里兼容 float 并向下取整
    start: Optional[float] = Query(None, ge=0, description="起始位置 (0-based)"),
    end: Optional[float] = Query(None, ge=0, description="结束位置"),
    lncrna: Optional[str] = Query(None, max_length=256, description="lncRNA 基因名过滤，如 CATG00000000011.1"),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max records to return (default: {DEFAULT_MAX_RECORDS_NO_REGION} when no region/lncrna filter)",
    ),
    db: Session = Depends(get_db),
):
    """
    流式导出调控关系为 BED 格式

    BED6 格式: chr, start, end, name, score, strand
    - name: lncRNA_name->target_name
    - score: binding_affinity (0-1000)
    - strand: . (unknown)

    支持区域查询和 lncRNA 过滤，优化 IGV 加载性能

    Args:
        species_id: 物种 ID
        chr: 可选，染色体过滤
        start: 可选，起始位置
        end: 可选，结束位置
        lncrna: 可选，lncRNA 基因名过滤（只返回该 lncRNA 的调控关系）

    Returns:
        StreamingResponse with BED format data
    """
    # 验证物种存在
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # 参数标准化：float -> int（向下取整）
    start_int = int(start) if start is not None else None
    end_int = int(end) if end is not None else None

    # 参数验证
    if (start_int is not None or end_int is not None) and chr is None:
        raise HTTPException(
            status_code=400,
            detail="chr parameter is required when using start/end filters"
        )

    if start_int is not None and end_int is not None and start_int >= end_int:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    if start_int is not None and end_int is not None and (end_int - start_int) > MAX_REGION_SIZE_BP:
        raise HTTPException(
            status_code=400,
            detail=f"region too large (max {MAX_REGION_SIZE_BP} bp)",
        )

    logger.info(
        "BED export requested: species=%s, chr=%s, start=%s, end=%s, lncrna=%s, limit=%s",
        species_id,
        sanitize_for_log(chr),
        start_int,
        end_int,
        sanitize_for_log(lncrna),
        limit,
    )

    has_region_filter = chr is not None and start_int is not None and end_int is not None
    if limit is not None:
        max_records = limit
    elif not has_region_filter and lncrna is None:
        max_records = DEFAULT_MAX_RECORDS_NO_REGION
    else:
        max_records = None

    # 生成 BED 数据流
    bed_stream = generate_bed_stream(
        db=db,
        species_id=species_id,
        chr_filter=chr,
        start_filter=start_int,
        end_filter=end_int,
        lncrna_filter=lncrna,
        max_records=max_records,
    )

    # 设置响应头
    filename = f"regulations_species{species_id}"
    if lncrna:
        filename = f"regulations_{lncrna}"
    if chr:
        filename += f"_{chr}"
        if start_int is not None and end_int is not None:
            filename += f"_{start_int}-{end_int}"
    filename += ".bed"

    return StreamingResponse(
        bed_stream,
        media_type="text/plain",
        headers={
            # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
            "Content-Disposition": content_disposition_attachment(filename),
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.get("/tracks/interactions/{species_id}.bedpe")
@rate_limit("60/minute")
def get_interactions_bedpe(
    request: Request,
    species_id: int,
    chr: Optional[str] = Query(None, max_length=64, description="染色体过滤，如 chr1"),
    # IGV.js webservice 轨道会传递浮点坐标（像素换算），这里兼容 float 并向下取整
    start: Optional[float] = Query(None, ge=0, description="起始位置 (0-based)"),
    end: Optional[float] = Query(None, ge=0, description="结束位置"),
    lncrna: Optional[str] = Query(None, max_length=256, description="lncRNA 基因名过滤，如 CATG00000000011.1"),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max records to return (default: {DEFAULT_MAX_RECORDS_NO_REGION} when no region/lncrna filter)",
    ),
    db: Session = Depends(get_db),
):
    """
    流式导出 lncRNA-Target 交互为 BEDPE 格式

    BEDPE 格式用于 IGV.js 的 interact 轨道，显示 lncRNA 与其结合位点之间的弧线连接。

    BEDPE 8列格式: chr1, start1, end1, chr2, start2, end2, name, score
    - Endpoint 1 (chr1/start1/end1): lncRNA 基因位置
    - Endpoint 2 (chr2/start2/end2): 结合位点位置 (best_peak)
    - name: lncRNA_name|target_name
    - score: binding_affinity (0-1000)

    支持区域查询和 lncRNA 过滤，优化 IGV 加载性能

    Args:
        species_id: 物种 ID
        chr: 可选，染色体过滤（匹配任一 endpoint）
        start: 可选，起始位置
        end: 可选，结束位置
        lncrna: 可选，lncRNA 基因名过滤（只返回该 lncRNA 的交互）

    Returns:
        StreamingResponse with BEDPE format data
    """
    # 验证物种存在
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    # 参数标准化：float -> int（向下取整）
    start_int = int(start) if start is not None else None
    end_int = int(end) if end is not None else None

    # 参数验证
    if (start_int is not None or end_int is not None) and chr is None:
        raise HTTPException(
            status_code=400,
            detail="chr parameter is required when using start/end filters"
        )

    if start_int is not None and end_int is not None and start_int >= end_int:
        raise HTTPException(
            status_code=400,
            detail="start must be less than end"
        )

    if start_int is not None and end_int is not None and (end_int - start_int) > MAX_REGION_SIZE_BP:
        raise HTTPException(
            status_code=400,
            detail=f"region too large (max {MAX_REGION_SIZE_BP} bp)",
        )

    logger.info(
        "BEDPE export requested: species=%s, chr=%s, start=%s, end=%s, lncrna=%s, limit=%s",
        species_id,
        sanitize_for_log(chr),
        start_int,
        end_int,
        sanitize_for_log(lncrna),
        limit,
    )

    has_region_filter = chr is not None and start_int is not None and end_int is not None
    if limit is not None:
        max_records = limit
    elif not has_region_filter and lncrna is None:
        max_records = DEFAULT_MAX_RECORDS_NO_REGION
    else:
        max_records = None

    # 生成 BEDPE 数据流
    bedpe_stream = generate_bedpe_stream(
        db=db,
        species_id=species_id,
        chr_filter=chr,
        start_filter=start_int,
        end_filter=end_int,
        lncrna_filter=lncrna,
        max_records=max_records,
    )

    # 设置响应头
    filename = f"interactions_species{species_id}"
    if lncrna:
        filename = f"interactions_{lncrna}"
    if chr:
        filename += f"_{chr}"
        if start_int is not None and end_int is not None:
            filename += f"_{start_int}-{end_int}"
    filename += ".bedpe"

    return StreamingResponse(
        bedpe_stream,
        media_type="text/plain",
        headers={
            # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
            "Content-Disposition": content_disposition_attachment(filename),
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
