"""
ChIP-seq Export API Router
数据导出功能端点
"""
import io
import csv
from typing import Optional
from itertools import combinations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.models import Gene
from app.schemas.chipseq import ExportFormat

# 从主路由导入 rate_limit 装饰器
from app.routers.chipseq import rate_limit, DEFAULT_FLANKING_REGION

router = APIRouter()


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
    include_overlaps: bool = Query(True, description="Include overlap data"),
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
    mark_list = [m.strip() for m in marks.split(",") if m.strip()]
    if len(mark_list) < 2:
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

    # Query peaks
    query = text("""
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
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
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

    # Calculate overlaps if requested
    overlaps_data = []
    if include_overlaps and len(marks_data) >= 2:
        mark_names = list(marks_data.keys())
        for mark_1, mark_2 in combinations(mark_names, 2):
            for p1 in marks_data[mark_1]:
                for p2 in marks_data[mark_2]:
                    if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
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

    # Generate output based on format
    if format == ExportFormat.json:
        import json
        output = json.dumps({
            "gene_id": gene_id,
            "gene_name": gene.gene_name,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "peaks": peaks_data,
            "overlaps": overlaps_data if include_overlaps else None,
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
                peak["peak_id"], peak["mark_type"], peak["mark_category"],
                peak["chromosome"], peak["peak_start"], peak["peak_end"],
                peak["summit_position"], peak["fold_enrichment"],
                peak["qvalue"], peak["peak_width"]
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
                    overlap["chromosome"], overlap["start"], overlap["end"],
                    overlap["length"], overlap["mark_1"], overlap["mark_2"],
                    overlap["mark_1_peak_id"], overlap["mark_2_peak_id"]
                ])

        output = output.getvalue()
        media_type = "text/csv" if format == ExportFormat.csv else "text/tab-separated-values"
        ext = "csv" if format == ExportFormat.csv else "tsv"
        filename = f"chipseq_compare_{gene_id}.{ext}"

    return StreamingResponse(
        io.BytesIO(output.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/genes/{gene_id}/overlaps/export")
def export_overlaps_bed(
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
        description="Filter by specific mark pair (e.g., 'H3K4me3:H3K27me3')"
    ),
    min_overlap_bp: int = Query(0, ge=0, description="Minimum overlap length"),
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
    mark_list = [m.strip() for m in marks.split(",") if m.strip()]
    if len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 marks are required for overlap detection"
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

    # Query peaks
    query = text("""
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
          AND p.peak_start < :region_end
          AND p.peak_end > :region_start
          AND e.is_active = TRUE
          AND m.mark_name = ANY(:mark_list)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
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

    # Find overlaps
    overlaps = []
    mark_names = list(marks_data.keys())

    # Parse mark_pair filter if provided
    filter_marks = None
    if mark_pair:
        filter_marks = set(mark_pair.split(":"))

    for mark_1, mark_2 in combinations(mark_names, 2):
        # Apply mark pair filter
        if filter_marks and {mark_1, mark_2} != filter_marks:
            continue

        for p1 in marks_data[mark_1]:
            for p2 in marks_data[mark_2]:
                if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
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

    # Sort by position
    overlaps.sort(key=lambda x: (x["chromosome"], x["start"]))

    # Generate output
    if format == ExportFormat.bed:
        output = io.StringIO()
        # BED header (optional track line)
        output.write(f"track name=\"ChIP-seq_Overlaps_{gene_id}\" description=\"Overlapping regions for gene {gene.gene_name}\"\n")
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
                o["chromosome"], o["start"], o["end"], o["name"],
                o["length"], o["mark_1"], o["mark_2"]
            ])
        media_type = "text/csv" if format == ExportFormat.csv else "text/tab-separated-values"
        ext = "csv" if format == ExportFormat.csv else "tsv"
        filename = f"chipseq_overlaps_{gene_id}.{ext}"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
