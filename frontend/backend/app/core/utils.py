"""
Shared utility functions for the application.
Consolidates common functionality to avoid code duplication.
"""
import re
from typing import Dict, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Species IDs for conservation calculations
# Human=1, Chimp=2, Macaque=3, Marmoset=4
SPECIES_IDS: List[int] = [1, 2, 3, 4]


def escape_like_pattern(value: str) -> str:
    """Escape LIKE pattern special characters (%, _, \\)"""
    return re.sub(r'([%_\\])', r'\\\1', value)


def compute_conservation_map(core_ids: List[int], db: "Session") -> Dict[int, tuple]:
    """
    Compute conservation data for a list of core_ids.

    This function determines the cross-species conservation status of genes
    by checking which species have the gene present.

    Args:
        core_ids: List of core gene IDs to check conservation for
        db: Database session

    Returns:
        Dict mapping core_id to (conservation_label, conservation_count)
        - conservation_label: Binary string like "1110" (present in human, chimp, macaque)
        - conservation_count: Number of species where the gene is present

    Example:
        >>> conservation_map = compute_conservation_map([123, 456], db)
        >>> conservation_map[123]
        ('1111', 4)  # Present in all 4 species
    """
    # Import here to avoid circular imports
    from app.models import Gene

    if not core_ids:
        return {}

    # Batch query: get species presence for all core_ids
    species_presence_query = db.query(Gene.core_id, Gene.species_id).filter(
        Gene.core_id.in_(core_ids)
    ).distinct()

    # Build a map: core_id -> set of species_ids
    species_map: Dict[int, Set[int]] = {}
    for core_id, species_id in species_presence_query.all():
        if core_id not in species_map:
            species_map[core_id] = set()
        species_map[core_id].add(species_id)

    # Convert to conservation labels
    result: Dict[int, tuple] = {}
    for core_id in core_ids:
        present_species = species_map.get(core_id, set())
        conservation_label = "".join(
            "1" if sid in present_species else "0"
            for sid in SPECIES_IDS
        )
        conservation_count = len(present_species)
        result[core_id] = (conservation_label, conservation_count)

    return result
