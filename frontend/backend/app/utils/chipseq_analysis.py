"""
ChIP-seq Analysis Utilities
分析算法和统计计算函数
"""
import statistics
from typing import List, Dict, Any

from app.schemas.chipseq import (
    OverlapRegion,
    CellLineOverlapRegion,
    PeakWidthPercentiles,
)


def calculate_percentiles(values: List[float], percentiles: List[float]) -> Dict[str, float]:
    """Calculate percentiles for a list of values"""
    if not values:
        return {f"p{int(p*100)}": None for p in percentiles}

    sorted_values = sorted(values)
    n = len(sorted_values)
    result = {}

    for p in percentiles:
        key = f"p{int(p*100)}"
        if n == 1:
            result[key] = sorted_values[0]
        else:
            idx = p * (n - 1)
            lower_idx = int(idx)
            upper_idx = min(lower_idx + 1, n - 1)
            weight = idx - lower_idx
            result[key] = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

    return result


def find_pairwise_overlaps(
    peaks_1: List[Dict],
    peaks_2: List[Dict],
    mark_1: str,
    mark_2: str,
    chromosome: str,
) -> List[OverlapRegion]:
    """
    Find overlapping regions between two sets of peaks.
    Uses a simple interval intersection algorithm.
    """
    overlaps = []

    # Sort peaks by start position for efficiency
    sorted_peaks_1 = sorted(peaks_1, key=lambda p: p["peak_start"])
    sorted_peaks_2 = sorted(peaks_2, key=lambda p: p["peak_start"])

    # Determine overlap type based on mark pair
    is_bivalent = (
        (mark_1 == "H3K4me3" and mark_2 == "H3K27me3") or
        (mark_1 == "H3K27me3" and mark_2 == "H3K4me3")
    )
    overlap_type = "bivalent" if is_bivalent else None

    for p1 in sorted_peaks_1:
        for p2 in sorted_peaks_2:
            # Early termination: if p2 starts after p1 ends, no more overlaps possible
            if p2["peak_start"] >= p1["peak_end"]:
                break

            # Check overlap
            if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
                overlap_start = max(p1["peak_start"], p2["peak_start"])
                overlap_end = min(p1["peak_end"], p2["peak_end"])

                overlaps.append(OverlapRegion(
                    chromosome=chromosome,
                    start=overlap_start,
                    end=overlap_end,
                    length=overlap_end - overlap_start,
                    mark_1=mark_1,
                    mark_2=mark_2,
                    mark_1_peak_id=p1["peak_id"],
                    mark_2_peak_id=p2["peak_id"],
                    overlap_type=overlap_type,
                ))

    return overlaps


def compute_mark_statistics(peaks: List[Dict], region_start: int, region_end: int) -> Dict[str, Any]:
    """
    Compute enhanced statistics for a mark's peaks.

    Returns:
        Dictionary with avg, median, std of fold_enrichment,
        total_coverage_bp, and peak_width_percentiles.
    """
    if not peaks:
        return {
            "avg_fold_enrichment": None,
            "median_fold_enrichment": None,
            "std_fold_enrichment": None,
            "total_coverage_bp": 0,
            "peak_width_percentiles": None,
        }

    # Fold enrichment statistics
    fe_values = [p["fold_enrichment"] for p in peaks if p["fold_enrichment"] is not None]
    avg_fe = statistics.mean(fe_values) if fe_values else None
    median_fe = statistics.median(fe_values) if fe_values else None
    std_fe = statistics.stdev(fe_values) if len(fe_values) > 1 else None

    # Total coverage (accounting for potential overlaps between peaks of same mark)
    # Use interval merging to avoid double-counting
    intervals = sorted([(p["peak_start"], p["peak_end"]) for p in peaks])
    merged = []
    for start, end in intervals:
        # Clip to region boundaries
        start = max(start, region_start)
        end = min(end, region_end)
        if start >= end:
            continue

        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    total_coverage_bp = sum(end - start for start, end in merged)

    # Peak width percentiles
    peak_widths = [p["peak_end"] - p["peak_start"] for p in peaks]
    width_percentiles = calculate_percentiles(peak_widths, [0.25, 0.50, 0.75])

    return {
        "avg_fold_enrichment": avg_fe,
        "median_fold_enrichment": median_fe,
        "std_fold_enrichment": std_fe,
        "total_coverage_bp": total_coverage_bp,
        "peak_width_percentiles": PeakWidthPercentiles(
            p25=width_percentiles.get("p25"),
            p50=width_percentiles.get("p50"),
            p75=width_percentiles.get("p75"),
        ),
    }


def find_cell_line_overlaps(
    peaks_1: List[Dict],
    peaks_2: List[Dict],
    cell_type_1: str,
    cell_type_2: str,
    chromosome: str,
) -> List[CellLineOverlapRegion]:
    """
    Find overlapping regions between two sets of peaks from different cell lines.
    Uses a simple interval intersection algorithm.
    """
    overlaps = []

    # Sort peaks by start position for efficiency
    sorted_peaks_1 = sorted(peaks_1, key=lambda p: p["peak_start"])
    sorted_peaks_2 = sorted(peaks_2, key=lambda p: p["peak_start"])

    for p1 in sorted_peaks_1:
        for p2 in sorted_peaks_2:
            # Early termination: if p2 starts after p1 ends, no more overlaps possible
            if p2["peak_start"] >= p1["peak_end"]:
                break

            # Check overlap
            if p1["peak_start"] < p2["peak_end"] and p1["peak_end"] > p2["peak_start"]:
                overlap_start = max(p1["peak_start"], p2["peak_start"])
                overlap_end = min(p1["peak_end"], p2["peak_end"])

                overlaps.append(CellLineOverlapRegion(
                    chromosome=chromosome,
                    start=overlap_start,
                    end=overlap_end,
                    length=overlap_end - overlap_start,
                    cell_type_1=cell_type_1,
                    cell_type_2=cell_type_2,
                    peak_id_1=p1["peak_id"],
                    peak_id_2=p2["peak_id"],
                ))

    return overlaps


def compute_jaccard_index(peaks_1: List[Dict], peaks_2: List[Dict]) -> float | None:
    """
    Compute Jaccard similarity index between two sets of peaks.
    Jaccard = Intersection / Union (based on base pairs)
    """
    if not peaks_1 or not peaks_2:
        return None

    # Merge intervals for set 1
    intervals_1 = sorted([(p["peak_start"], p["peak_end"]) for p in peaks_1])
    merged_1 = []
    for start, end in intervals_1:
        if merged_1 and start <= merged_1[-1][1]:
            merged_1[-1] = (merged_1[-1][0], max(merged_1[-1][1], end))
        else:
            merged_1.append((start, end))

    # Merge intervals for set 2
    intervals_2 = sorted([(p["peak_start"], p["peak_end"]) for p in peaks_2])
    merged_2 = []
    for start, end in intervals_2:
        if merged_2 and start <= merged_2[-1][1]:
            merged_2[-1] = (merged_2[-1][0], max(merged_2[-1][1], end))
        else:
            merged_2.append((start, end))

    # Compute union and intersection
    # Union: merge both sets together
    all_intervals = sorted(merged_1 + merged_2)
    union_merged = []
    for start, end in all_intervals:
        if union_merged and start <= union_merged[-1][1]:
            union_merged[-1] = (union_merged[-1][0], max(union_merged[-1][1], end))
        else:
            union_merged.append((start, end))
    union_bp = sum(end - start for start, end in union_merged)

    # Intersection: find overlapping regions between the two merged sets
    intersection_bp = 0
    i, j = 0, 0
    while i < len(merged_1) and j < len(merged_2):
        start1, end1 = merged_1[i]
        start2, end2 = merged_2[j]

        # Check for overlap
        if start1 < end2 and start2 < end1:
            intersection_bp += min(end1, end2) - max(start1, start2)

        # Move pointer for the interval that ends first
        if end1 <= end2:
            i += 1
        else:
            j += 1

    if union_bp == 0:
        return None

    return intersection_bp / union_bp


def find_common_peaks(cell_lines_data: Dict[str, Dict], chromosome: str) -> int:
    """
    Find peaks that overlap with at least one peak in every cell line.
    Returns count of such peaks from the first cell line.
    """
    if len(cell_lines_data) < 2:
        return 0

    cell_types = list(cell_lines_data.keys())
    first_cell_type = cell_types[0]
    first_peaks = cell_lines_data[first_cell_type]["peaks"]

    common_count = 0
    for peak in first_peaks:
        # Check if this peak overlaps with at least one peak in every other cell line
        overlaps_all = True
        for cell_type in cell_types[1:]:
            other_peaks = cell_lines_data[cell_type]["peaks"]
            has_overlap = False
            for other_peak in other_peaks:
                if (peak["peak_start"] < other_peak["peak_end"] and
                    peak["peak_end"] > other_peak["peak_start"]):
                    has_overlap = True
                    break
            if not has_overlap:
                overlaps_all = False
                break

        if overlaps_all:
            common_count += 1

    return common_count
