import pytest


pytestmark = pytest.mark.unit


def test_reference_genome_aliases_hg19_includes_grch37() -> None:
    from app.core.genome_assembly import reference_genome_aliases

    aliases = reference_genome_aliases("hg19")
    assert "hg19" in aliases
    assert "grch37" in aliases


def test_reference_genome_compatibility_treats_null_as_compatible() -> None:
    from app.core.genome_assembly import is_reference_genome_compatible

    assert is_reference_genome_compatible(None, expected_assembly="hg19") is True


def test_reference_genome_compatibility_excludes_grch38_for_hg19() -> None:
    from app.core.genome_assembly import is_reference_genome_compatible

    assert is_reference_genome_compatible("GRCh38", expected_assembly="hg19") is False
