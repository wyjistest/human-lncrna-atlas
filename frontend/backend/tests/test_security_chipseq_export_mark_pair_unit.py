import pytest

from fastapi import HTTPException

from app.routers.chipseq_export import _parse_mark_pair_filter


pytestmark = pytest.mark.unit


def test_parse_mark_pair_none_returns_none():
    assert _parse_mark_pair_filter(None, ["H3K4me3", "H3K27me3"]) is None


def test_parse_mark_pair_valid_returns_set():
    result = _parse_mark_pair_filter(" H3K4me3 : H3K27me3 ", ["H3K4me3", "H3K27me3", "H3K27ac"])
    assert result == {"H3K4me3", "H3K27me3"}


@pytest.mark.parametrize(
    "mark_pair",
    [
        "H3K4me3",  # missing ':'
        "H3K4me3:",  # missing second mark
        ":H3K27me3",  # missing first mark
        "H3K4me3:H3K27me3:EXTRA",  # too many segments
        "H3K4me3:H3K4me3",  # duplicate marks
    ],
)
def test_parse_mark_pair_invalid_format_raises_400(mark_pair: str):
    with pytest.raises(HTTPException) as exc:
        _parse_mark_pair_filter(mark_pair, ["H3K4me3", "H3K27me3"])
    assert exc.value.status_code == 400


def test_parse_mark_pair_marks_must_be_in_marks_param():
    with pytest.raises(HTTPException) as exc:
        _parse_mark_pair_filter("H3K4me3:H3K27me3", ["H3K4me3"])
    assert exc.value.status_code == 400

