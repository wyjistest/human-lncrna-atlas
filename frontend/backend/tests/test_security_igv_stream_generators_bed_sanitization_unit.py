"""
Unit tests: IGV stream generators should sanitize BED/track text output.

Goal:
- Prevent control characters in output fields from breaking BED/TSV structure (tab/newline/null).
"""

from types import SimpleNamespace

import pytest

from app.core.igv_stream_generators import (
    generate_bed_stream,
    generate_bedpe_stream,
    generate_chipseq_bed_stream,
    generate_empty_chipseq_bed_stream,
    generate_repeatmasker_bed_stream,
)
from app.models import EpigeneticMarkType, FeatureTrack


pytestmark = pytest.mark.unit


class _FakeQuery:
    def __init__(self, *, rows=None, first_row=None):
        self._rows = list(rows or [])
        self._first_row = first_row

    def join(self, *args, **kwargs):  # noqa: ARG002
        return self

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def order_by(self, *args, **kwargs):  # noqa: ARG002
        return self

    def execution_options(self, **kwargs):  # noqa: ARG002
        return self

    def yield_per(self, batch_size):  # noqa: ARG002
        return self

    def first(self):
        return self._first_row

    def __iter__(self):
        return iter(self._rows)


class _DummySession:
    def __init__(self, rows):
        self._rows = rows

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def query(self, *args, **kwargs):  # noqa: ARG002
        if len(args) == 1 and args[0] is FeatureTrack:
            return _FakeQuery(first_row=SimpleNamespace(track_id=1))
        if len(args) == 1 and args[0] is EpigeneticMarkType:
            return _FakeQuery(first_row=SimpleNamespace(mark_type_id=1))
        return _FakeQuery(rows=self._rows)


def _assert_no_control_chars(text: str) -> None:
    assert "\t" not in text
    assert "\r" not in text
    assert "\n" not in text
    assert "\x00" not in text


def test_generate_bed_stream_sanitizes_name_field():
    db = _DummySession(
        [
            SimpleNamespace(
                best_peak_chr="chr1",
                best_peak_start=0,
                best_peak_end=10,
                binding_affinity=12.3,
                lncrna_name="LNC\tBAD",
                target_name="TGT\nBAD",
            )
        ]
    )

    line = next(generate_bed_stream(db=db, species_id=1))
    fields = line.rstrip("\n").split("\t")
    assert len(fields) == 6
    _assert_no_control_chars(fields[3])


def test_generate_bedpe_stream_sanitizes_name_field():
    db = _DummySession(
        [
            SimpleNamespace(
                chr1="chr1",
                start1=100,
                end1=200,
                chr2="chr1",
                start2=300,
                end2=400,
                lncrna_name="LNC\rBAD",
                target_name="TGT\x00BAD",
                binding_affinity=99.9,
            )
        ]
    )

    line = next(generate_bedpe_stream(db=db, species_id=1))
    fields = line.rstrip("\n").split("\t")
    assert len(fields) == 8
    _assert_no_control_chars(fields[6])


def test_generate_repeatmasker_bed_stream_sanitizes_feature_name():
    db = _DummySession(
        [
            SimpleNamespace(
                chromosome="chr1",
                feature_start=1,
                feature_end=2,
                feature_name="Alu\tX\n",
                strand="+",
                attributes={"divergence": 1.0},
            )
        ]
    )

    line = next(generate_repeatmasker_bed_stream(db=db, species_id=1))
    fields = line.rstrip("\n").split("\t")
    assert len(fields) == 6
    _assert_no_control_chars(fields[3])


def test_generate_chipseq_bed_stream_sanitizes_name_field():
    db = _DummySession(
        [
            SimpleNamespace(
                chromosome="chr1",
                peak_start=10,
                peak_end=20,
                peak_name="peak\tname\r\n",
                fold_enrichment=2.5,
                strand=None,
                neg_log10_pvalue=1.23,
                neg_log10_qvalue=0.45,
            )
        ]
    )

    line = next(generate_chipseq_bed_stream(db=db, species_id=1, mark_type="H3K27me3\nBAD"))
    fields = line.rstrip("\n").split("\t")
    assert len(fields) == 9
    _assert_no_control_chars(fields[3])


def test_generate_empty_chipseq_bed_stream_sanitizes_track_header_attributes():
    line = next(generate_empty_chipseq_bed_stream(mark_type='H3K27me3"\r\nbad', species_name="Homo\nsapiens"))
    body = line.rstrip("\n")

    assert body.startswith("# track ")
    _assert_no_control_chars(body)
    # Only the attribute delimiters should remain.
    assert body.count('"') == 4

