import gzip
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def test_validate_peak_file_flags_out_of_bounds(tmp_path: Path) -> None:
    from scripts.genomes.validate_peak_bed_bounds import validate_peak_file

    chrom_sizes = {"chr1": 100}
    bed = tmp_path / "peaks.bed"
    bed.write_text("chr1\t0\t50\nchr1\t0\t101\n", encoding="utf-8")

    ok, stats, examples = validate_peak_file(
        bed, chrom_sizes=chrom_sizes, allow_unknown_chroms=False, max_examples=3
    )

    assert ok is False
    assert stats["records"] == 2
    assert stats["bad_records"] == 1
    assert len(examples) >= 1


def test_validate_peak_file_allows_unknown_chroms_when_configured(tmp_path: Path) -> None:
    from scripts.genomes.validate_peak_bed_bounds import validate_peak_file

    chrom_sizes = {"chr1": 100}
    bed = tmp_path / "peaks.bed"
    bed.write_text("chrUn\t0\t10\nchr1\t0\t50\n", encoding="utf-8")

    ok, stats, _ = validate_peak_file(
        bed, chrom_sizes=chrom_sizes, allow_unknown_chroms=True, max_examples=3
    )

    assert ok is True
    assert stats["records"] == 2
    assert stats["unknown_chrom_records"] == 1


def test_validate_peak_file_supports_gz(tmp_path: Path) -> None:
    from scripts.genomes.validate_peak_bed_bounds import validate_peak_file

    chrom_sizes = {"chr1": 100}
    bed_gz = tmp_path / "peaks.bed.gz"
    with gzip.open(bed_gz, "wt", encoding="utf-8") as fh:
        fh.write("chr1\t0\t50\n")

    ok, stats, _ = validate_peak_file(
        bed_gz, chrom_sizes=chrom_sizes, allow_unknown_chroms=False, max_examples=3
    )

    assert ok is True
    assert stats["records"] == 1
