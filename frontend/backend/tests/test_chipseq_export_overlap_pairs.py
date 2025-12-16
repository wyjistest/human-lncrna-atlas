import pytest

# Mark all tests in this module as unit tests (pure logic, no external deps)
pytestmark = pytest.mark.unit


def _naive_overlap_pairs(peaks_a, peaks_b):
    for peak_a in peaks_a:
        for peak_b in peaks_b:
            if peak_a["peak_start"] < peak_b["peak_end"] and peak_a["peak_end"] > peak_b["peak_start"]:
                yield peak_a, peak_b


def test_iter_overlapping_peak_pairs_matches_naive():
    from app.routers.chipseq_export import _iter_overlapping_peak_pairs

    peaks_a = [
        {"peak_id": 1, "peak_start": 10, "peak_end": 20},
        {"peak_id": 2, "peak_start": 30, "peak_end": 40},
        {"peak_id": 3, "peak_start": 50, "peak_end": 60},
    ]
    peaks_b = [
        {"peak_id": 101, "peak_start": 5, "peak_end": 9},    # no overlap
        {"peak_id": 102, "peak_start": 18, "peak_end": 22},  # overlaps peak 1
        {"peak_id": 103, "peak_start": 35, "peak_end": 45},  # overlaps peak 2
        {"peak_id": 104, "peak_start": 60, "peak_end": 70},  # touching end, no overlap
    ]

    expected = [(a["peak_id"], b["peak_id"]) for a, b in _naive_overlap_pairs(peaks_a, peaks_b)]
    got = [(a["peak_id"], b["peak_id"]) for a, b in _iter_overlapping_peak_pairs(peaks_a, peaks_b)]
    assert got == expected


def test_iter_overlapping_peak_pairs_handles_overlaps_within_same_list():
    from app.routers.chipseq_export import _iter_overlapping_peak_pairs

    peaks_a = [
        {"peak_id": 1, "peak_start": 10, "peak_end": 30},
        {"peak_id": 2, "peak_start": 20, "peak_end": 40},  # overlaps peak 1
    ]
    peaks_b = [
        {"peak_id": 101, "peak_start": 25, "peak_end": 26},  # overlaps both peaks in A
    ]

    expected = [(a["peak_id"], b["peak_id"]) for a, b in _naive_overlap_pairs(peaks_a, peaks_b)]
    got = [(a["peak_id"], b["peak_id"]) for a, b in _iter_overlapping_peak_pairs(peaks_a, peaks_b)]
    assert got == expected

