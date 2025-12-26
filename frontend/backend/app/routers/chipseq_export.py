"""
ChIP-seq Export API Router
数据导出功能端点

Phase 9.11 改进:
- include_overlaps 默认关闭（资源密集型操作）
- 添加 marks 数量限制（最多 10 个）
- CSV/TSV 输出添加公式注入防护
- max_rows 参数限制 SQL 查询返回的 peak 数量（默认 10000，最大 50000）
- max_overlaps 参数限制重叠计算数量（默认 10000，最大 50000），防止 O(n²) 内存爆炸
- JSON 输出包含 peaks_truncated/overlaps_truncated 标志，指示数据是否被截断

内存保护策略:
  1. SQL LIMIT :max_rows 在数据库层面限制 peak 数量
  2. max_overlaps 在计算层面限制重叠对数量（early-break）
  3. 使用共享验证器限制 marks 数量和长度
"""
import io
import csv
import logging
from typing import Optional, Iterator, Tuple, Dict, Any
from itertools import combinations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error
from app.core.validators import MAX_EXPORT_MARKS, parse_comma_list
from app.models import Gene
from app.schemas.chipseq import ExportFormat
from app.utils.bed import sanitize_bed_track_attr
from app.utils.http_headers import content_disposition_attachment
from app.utils.streaming_export import sanitize_csv_value

# 从共享模块导入 rate_limit 装饰器（避免与主路由形成循环依赖）
from app.routers.chipseq_rate_limit import rate_limit, DEFAULT_FLANKING_REGION

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_mark_pair_filter(mark_pair: Optional[str], mark_list: list[str]) -> Optional[set[str]]:
    """
    Parse and validate the optional mark_pair filter.

    Expected format: "mark1:mark2" (exactly 2 marks).
    Both marks must be present in the `marks` parameter (mark_list).
    """
    if not mark_pair:
        return None

    raw = mark_pair.strip()
    if not raw:
        return None

    parts = [p.strip() for p in raw.split(":") if p.strip()]
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="mark_pair must be in format 'mark1:mark2'")
    mark_a, mark_b = parts
    if mark_a == mark_b:
        raise HTTPException(status_code=400, detail="mark_pair must contain two different marks")
    if mark_a not in mark_list or mark_b not in mark_list:
        raise HTTPException(status_code=400, detail="mark_pair marks must be included in the 'marks' parameter")
    return {mark_a, mark_b}


def _iter_overlapping_peak_pairs(
    peaks_a: list[Dict[str, Any]],
    peaks_b: list[Dict[str, Any]],
) -> Iterator[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    迭代返回两个 peak 列表中相互重叠的 peak 对。

    说明：
    - 输入列表必须按 `peak_start` 升序排序（SQL 查询已保证）
    - 算法为滑动窗口，避免 O(n*m) 全量笛卡尔比较
    """
    j = 0
    for peak_a in peaks_a:
        start_a = peak_a["peak_start"]
        end_a = peak_a["peak_end"]

        while j < len(peaks_b) and peaks_b[j]["peak_end"] <= start_a:
            j += 1

        k = j
        while k < len(peaks_b) and peaks_b[k]["peak_start"] < end_a:
            yield peak_a, peaks_b[k]
            k += 1


@router.get("/genes/{gene_id}/compare/export")
@rate_limit("5/minute")  # Rate limit: 5 requests per minute per IP (export is resource-intensive)
def export_comparison(
    request: Request,  # Required for rate limiting
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
    include_overlaps: bool = Query(False, description="Include overlap data (resource-intensive, disabled by default)"),
    max_rows: int = Query(10000, ge=1, le=50000, description="Maximum number of peaks to return (prevents memory issues)"),
    max_overlaps: int = Query(10000, ge=1, le=50000, description="Maximum number of overlaps to compute (prevents O(n²) explosion)"),
    db: Session = Depends(get_db),
):
    """
    Export comparison data in CSV, TSV, or JSON format (Phase 2.5)

    Downloads the comparison results for further analysis in external tools.

    **Rate Limit:** 5 requests per minute per IP (export endpoints are resource-intensive).

    **Example:**
    ```
    GET /features/chipseq/genes/12345/compare/export?marks=H3K27me3,H3K4me3&format=csv
    ```
    """
    # Get comparison data (reuse existing logic)
    # Phase 9.11: 使用共享验证器，统一输入长度/项数限制
    mark_list = parse_comma_list(marks, max_items=MAX_EXPORT_MARKS, param_name="marks")
    if not mark_list or len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 marks are required for comparison"
        )

    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    qvalue_clause = "(p.qvalue IS NULL OR p.qvalue <= :max_qvalue)" if max_qvalue is not None else "TRUE"
    region_predicate = (
        "int8range(p.peak_start, p.peak_end, '[)') && int8range(:region_start, :region_end, '[)')"
        if db.get_bind().dialect.name == "postgresql"
        else "p.peak_start < :region_end AND p.peak_end > :region_start"
    )

    # Query peaks (Phase 9.11: 添加 LIMIT 防止内存溢出)
    query = text(
        f"""
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
          AND {region_predicate}
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND {qvalue_clause}
        ORDER BY m.mark_name, p.peak_start
        LIMIT :max_rows
        """  # noqa: S608
    )

    try:
        rows = db.execute(
            query,
            {
                "species_id": gene.species_id,
                "chromosome": gene.chromosome,
                "region_start": region_start,
                "region_end": region_end,
                "mark_list": mark_list,
                "max_qvalue": max_qvalue,
                "max_rows": max_rows,
            },
        ).fetchall()
    except Exception as e:
        raise sanitize_db_error(e, logger)

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

    # Calculate overlaps if requested (Phase 9.11: max_overlaps 防止 O(n²) 内存爆炸)
    overlaps_data = []
    overlaps_truncated = False
    if include_overlaps and len(marks_data) >= 2:
        mark_names = list(marks_data.keys())
        for mark_1, mark_2 in combinations(mark_names, 2):
            if len(overlaps_data) >= max_overlaps:
                overlaps_truncated = True
                break
            for p1, p2 in _iter_overlapping_peak_pairs(marks_data[mark_1], marks_data[mark_2]):
                if len(overlaps_data) >= max_overlaps:
                    overlaps_truncated = True
                    break
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
            if overlaps_truncated:
                break

    # Generate output based on format
    peaks_truncated = len(peaks_data) >= max_rows
    if format == ExportFormat.json:
        import json
        output = json.dumps({
            "gene_id": gene_id,
            "gene_name": gene.gene_name,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "peaks": peaks_data,
            "peaks_truncated": peaks_truncated,
            "overlaps": overlaps_data if include_overlaps else None,
            "overlaps_truncated": overlaps_truncated if include_overlaps else None,
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
                sanitize_csv_value(peak["peak_id"]),
                sanitize_csv_value(peak["mark_type"]),
                sanitize_csv_value(peak["mark_category"]),
                sanitize_csv_value(peak["chromosome"]),
                sanitize_csv_value(peak["peak_start"]),
                sanitize_csv_value(peak["peak_end"]),
                sanitize_csv_value(peak["summit_position"]),
                sanitize_csv_value(peak["fold_enrichment"]),
                sanitize_csv_value(peak["qvalue"]),
                sanitize_csv_value(peak["peak_width"])
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
                    sanitize_csv_value(overlap["chromosome"]),
                    sanitize_csv_value(overlap["start"]),
                    sanitize_csv_value(overlap["end"]),
                    sanitize_csv_value(overlap["length"]),
                    sanitize_csv_value(overlap["mark_1"]),
                    sanitize_csv_value(overlap["mark_2"]),
                    sanitize_csv_value(overlap["mark_1_peak_id"]),
                    sanitize_csv_value(overlap["mark_2_peak_id"])
                ])

        output = output.getvalue()
        media_type = "text/csv" if format == ExportFormat.csv else "text/tab-separated-values"
        ext = "csv" if format == ExportFormat.csv else "tsv"
        filename = f"chipseq_compare_{gene_id}.{ext}"

    return StreamingResponse(
        io.BytesIO(output.encode("utf-8")),
        media_type=media_type,
        # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


@router.get("/genes/{gene_id}/overlaps/export")
@rate_limit("5/minute")
def export_overlaps_bed(
    request: Request,
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
        max_length=200,
        description="Filter by specific mark pair (e.g., 'H3K4me3:H3K27me3')"
    ),
    min_overlap_bp: int = Query(0, ge=0, description="Minimum overlap length"),
    max_rows: int = Query(10000, ge=1, le=50000, description="Maximum number of peaks to query (prevents memory issues)"),
    max_overlaps: int = Query(10000, ge=1, le=50000, description="Maximum number of overlaps to compute (prevents O(n²) explosion)"),
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
    # Phase 9.11: 使用共享验证器，统一输入长度/项数限制
    mark_list = parse_comma_list(marks, max_items=MAX_EXPORT_MARKS, param_name="marks")
    if not mark_list or len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 marks are required for overlap detection"
        )

    filter_marks = _parse_mark_pair_filter(mark_pair, mark_list)

    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    qvalue_clause = "(p.qvalue IS NULL OR p.qvalue <= :max_qvalue)" if max_qvalue is not None else "TRUE"
    region_predicate = (
        "int8range(p.peak_start, p.peak_end, '[)') && int8range(:region_start, :region_end, '[)')"
        if db.get_bind().dialect.name == "postgresql"
        else "p.peak_start < :region_end AND p.peak_end > :region_start"
    )

    # Query peaks (Phase 9.11: 添加 LIMIT 防止内存溢出)
    query = text(
        f"""
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
          AND {region_predicate}
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND {qvalue_clause}
        ORDER BY m.mark_name, p.peak_start
        LIMIT :max_rows
        """  # noqa: S608
    )

    try:
        rows = db.execute(
            query,
            {
                "species_id": gene.species_id,
                "chromosome": gene.chromosome,
                "region_start": region_start,
                "region_end": region_end,
                "mark_list": mark_list,
                "max_qvalue": max_qvalue,
                "max_rows": max_rows,
            },
        ).fetchall()
    except Exception as e:
        raise sanitize_db_error(e, logger)

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

    # Find overlaps (Phase 9.11: max_overlaps 防止 O(n²) 内存爆炸)
    overlaps = []
    overlaps_truncated = False
    mark_names = list(marks_data.keys())

    for mark_1, mark_2 in combinations(mark_names, 2):
        if len(overlaps) >= max_overlaps:
            overlaps_truncated = True
            break

        # Apply mark pair filter
        if filter_marks and {mark_1, mark_2} != filter_marks:
            continue

        for p1, p2 in _iter_overlapping_peak_pairs(marks_data[mark_1], marks_data[mark_2]):
            if len(overlaps) >= max_overlaps:
                overlaps_truncated = True
                break
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
        if overlaps_truncated:
            break

    # Sort by position
    overlaps.sort(key=lambda x: (x["chromosome"], x["start"]))

    # Generate output
    if format == ExportFormat.bed:
        output = io.StringIO()
        # BED header (optional track line)
        safe_gene_name = sanitize_bed_track_attr(gene.gene_name or "unknown")
        output.write(
            f"track name=\"ChIP-seq_Overlaps_{gene_id}\" description=\"Overlapping regions for gene {safe_gene_name}\"\n"
        )
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
            "overlaps_truncated": overlaps_truncated,
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
                sanitize_csv_value(o["chromosome"]),
                sanitize_csv_value(o["start"]),
                sanitize_csv_value(o["end"]),
                sanitize_csv_value(o["name"]),
                sanitize_csv_value(o["length"]),
                sanitize_csv_value(o["mark_1"]),
                sanitize_csv_value(o["mark_2"])
            ])
        media_type = "text/csv" if format == ExportFormat.csv else "text/tab-separated-values"
        ext = "csv" if format == ExportFormat.csv else "tsv"
        filename = f"chipseq_overlaps_{gene_id}.{ext}"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type=media_type,
        # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )
