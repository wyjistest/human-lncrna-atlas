import pytest

from app.core.config import settings
from app.core.igv_utils import get_genome_reference


pytestmark = pytest.mark.unit


def test_hg19_reference_uses_builtin_genome_when_no_local_twobit(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "GENOMES_DIR", str(tmp_path), raising=False)

    ref = get_genome_reference(1)

    assert ref.id == "hg19"
    assert ref.twoBitURL is None
    assert ref.chromSizesURL is None
    assert ref.cytobandURL is None
    assert ref.aliasURL is None


def test_hg19_reference_switches_to_local_files_when_available(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "hg19.2bit").write_bytes(b"00FAKE2BIT")
    (tmp_path / "hg19.chrom.sizes").write_text("chr1\t249250621\n", encoding="utf-8")
    (tmp_path / "cytoBand.hg19.txt.gz").write_bytes(b"\x1f\x8bFAKEGZ")
    (tmp_path / "hg19_alias.tab").write_text("chrM\tMT\n", encoding="utf-8")

    monkeypatch.setattr(settings, "GENOMES_DIR", str(tmp_path), raising=False)

    ref = get_genome_reference(1)

    assert ref.id == "hg19"
    assert ref.twoBitURL == "/genomes/hg19.2bit"
    assert ref.chromSizesURL == "/genomes/hg19.chrom.sizes"
    assert ref.cytobandURL == "/genomes/cytoBand.hg19.txt.gz"
    assert ref.aliasURL == "/genomes/hg19_alias.tab"

