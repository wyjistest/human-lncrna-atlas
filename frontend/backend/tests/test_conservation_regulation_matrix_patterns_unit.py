"""
Unit tests: conservation regulation matrix pattern expansion

Phase 9.41:
- /conservation/matrix 和 /conservation/venn(regulation) 由 SQL 聚合得到 4-bit pattern_counts
- 在 Python 侧把 pattern_counts 扩展为 4x4 regulation_matrix
"""

import pytest

from app.routers.conservation import _build_regulation_matrix_from_pattern_counts


pytestmark = pytest.mark.unit


def test_build_regulation_matrix_from_pattern_counts():
    # label bits follow SPECIES_IDS order: [1,2,3,4] -> positions [0,1,2,3]
    pattern_counts = {
        "1000": 2,
        "1100": 3,
        "0110": 4,
        "1111": 1,
        "": 999,        # ignored
        "111": 999,     # ignored
        "00000": 999,   # ignored
    }

    matrix = _build_regulation_matrix_from_pattern_counts(pattern_counts)

    # Diagonals: sum of all patterns where that species bit is 1
    assert matrix[0][0] == 2 + 3 + 1
    assert matrix[1][1] == 3 + 4 + 1
    assert matrix[2][2] == 4 + 1
    assert matrix[3][3] == 1

    # Off-diagonals: sum of patterns where both bits are 1
    assert matrix[0][1] == 3 + 1
    assert matrix[1][2] == 4 + 1
    assert matrix[0][3] == 1

    # Symmetry
    assert matrix[1][0] == matrix[0][1]
    assert matrix[2][1] == matrix[1][2]
    assert matrix[3][0] == matrix[0][3]

