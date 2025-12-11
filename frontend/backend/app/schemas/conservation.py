"""
Conservation Analysis Data Models (Pydantic Schemas)
Cross-species conservation analysis for lncRNA regulatory networks
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from typing import Annotated
from pydantic import PlainSerializer

# Decimal serializer (consistent with regulation.py)
DecimalAsFloat = Annotated[
    Decimal,
    PlainSerializer(lambda x: float(x) if x is not None else None, return_type=float)
]

# =============================================================================
# Species Constants
# =============================================================================
SPECIES_MAP = {
    1: "Human",
    2: "Chimp",
    3: "Macaque",
    4: "Marmoset"
}

SPECIES_IDS = [1, 2, 3, 4]


# =============================================================================
# Conservation Summary Models
# =============================================================================
class ConservationDistribution(BaseModel):
    """Conservation level distribution"""

    conservation_count: int = Field(description="Number of species (1-4)")
    lncrna_count: int = Field(description="Number of lncRNAs with this conservation level")
    regulation_count: int = Field(description="Number of regulations at this level")
    percentage: float = Field(description="Percentage of total")


class SpeciesCombinationStats(BaseModel):
    """Statistics for a specific species combination"""

    combination_label: str = Field(description="4-bit binary label (e.g., '1101')")
    species_names: List[str] = Field(description="List of species in this combination")
    species_count: int = Field(description="Number of species in combination")
    lncrna_count: int = Field(description="Number of lncRNAs in this combination")
    regulation_count: int = Field(description="Number of regulations in this combination")


class ConservationSummary(BaseModel):
    """Overall conservation summary statistics"""

    total_lncrnas: int = Field(description="Total number of lncRNAs")
    total_regulations: int = Field(description="Total number of regulations")

    # Distribution by conservation level (1-4 species)
    distribution: List[ConservationDistribution] = Field(
        description="Distribution by conservation level"
    )

    # Top species combinations
    top_combinations: List[SpeciesCombinationStats] = Field(
        description="Statistics for each species combination"
    )

    # Summary metrics
    fully_conserved_count: int = Field(
        description="Number of lncRNAs conserved in all 4 species"
    )
    primate_specific_count: int = Field(
        description="Number of lncRNAs unique to one species"
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Single LncRNA Conservation Models
# =============================================================================
class SpeciesRegulationInfo(BaseModel):
    """Regulation information for a single species"""

    species_id: int
    species_name: str
    gene_id: Optional[int] = Field(description="Gene ID in this species")
    gene_name: Optional[str] = Field(description="Gene name in this species")
    gene_ensembl_id: Optional[str] = Field(description="Ensembl ID in this species")
    target_count: int = Field(description="Number of targets in this species")
    avg_binding_affinity: Optional[float] = Field(
        description="Average binding affinity"
    )


class ConservedTarget(BaseModel):
    """A target gene conserved across species"""

    target_core_id: int = Field(description="Core ID of the target gene")
    target_symbol: Optional[str] = Field(description="Gene symbol")
    conservation_label: str = Field(description="4-bit conservation pattern")
    conservation_count: int = Field(description="Number of species with this target")
    species_details: Dict[int, Dict[str, Any]] = Field(
        description="Per-species details: {species_id: {gene_id, binding_affinity}}"
    )


class LncRNAConservation(BaseModel):
    """Conservation data for a single lncRNA"""

    core_id: int = Field(description="Core ID of the lncRNA")
    canonical_symbol: Optional[str] = Field(description="Canonical gene symbol")
    human_ensembl_id: Optional[str] = Field(description="Human Ensembl ID")

    # Conservation pattern
    conservation_label: str = Field(
        description="4-bit binary: position 1=Human, 2=Chimp, 3=Macaque, 4=Marmoset"
    )
    conservation_count: int = Field(description="Number of species (1-4)")

    # Per-species information
    species_info: List[SpeciesRegulationInfo] = Field(
        description="Regulation info for each species"
    )

    # Target analysis
    total_unique_targets: int = Field(description="Total unique target core_ids")
    conserved_targets: List[ConservedTarget] = Field(
        description="Targets conserved across 2+ species"
    )
    conserved_target_count: int = Field(
        description="Number of targets in 2+ species"
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Species Comparison Models
# =============================================================================
class SpeciesComparisonRegulation(BaseModel):
    """A regulation in the species comparison"""

    lncrna_core_id: int
    lncrna_symbol: Optional[str]
    target_core_id: int
    target_symbol: Optional[str]
    species_present: Dict[int, bool] = Field(
        description="Which species have this regulation"
    )
    binding_affinities: Dict[int, Optional[float]] = Field(
        description="Binding affinity per species"
    )


class SpeciesComparisonResult(BaseModel):
    """Result of comparing regulations between selected species"""

    selected_species: List[int] = Field(description="List of selected species IDs")
    selected_species_names: List[str] = Field(description="Names of selected species")

    # Statistics
    total_lncrnas: int = Field(description="Total lncRNAs in comparison")
    conserved_regulations: int = Field(
        description="Regulations present in ALL selected species"
    )
    partial_regulations: int = Field(
        description="Regulations present in SOME (but not all) selected species"
    )

    # Jaccard similarity between species pairs
    pairwise_similarity: Dict[str, float] = Field(
        description="Jaccard similarity: {'1_2': 0.45, '1_3': 0.38, ...}"
    )

    # Sample conserved regulations (paginated in actual API)
    conserved_sample: List[SpeciesComparisonRegulation] = Field(
        default_factory=list,
        description="Sample of conserved regulations"
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Conservation Matrix Models
# =============================================================================
class MatrixCell(BaseModel):
    """A cell in the conservation matrix"""

    species_1: int
    species_2: int
    shared_lncrnas: int = Field(description="LncRNAs present in both species")
    shared_regulations: int = Field(description="Regulations conserved between species")
    jaccard_index: float = Field(description="Jaccard similarity index (0-1)")


class ConservationMatrix(BaseModel):
    """Species-to-species conservation matrix for heatmap visualization"""

    species: List[Dict[str, Any]] = Field(
        description="Species info: [{id: 1, name: 'Human'}, ...]"
    )

    # Matrix data
    lncrna_matrix: List[List[int]] = Field(
        description="4x4 matrix: shared lncRNA counts"
    )
    regulation_matrix: List[List[int]] = Field(
        description="4x4 matrix: shared regulation counts"
    )
    jaccard_matrix: List[List[float]] = Field(
        description="4x4 matrix: Jaccard similarity"
    )

    # Additional stats
    diagonal_totals: Dict[int, int] = Field(
        description="Total counts per species (diagonal values)"
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Paginated Response for Conserved Regulations
# =============================================================================
class SpeciesBindingAffinity(BaseModel):
    """Binding affinity for a specific species"""
    species_id: int
    species_name: str
    binding_affinity: Optional[float]


class ConservedRegulationItem(BaseModel):
    """Item in conserved regulation list - matches frontend ConservedRegulation interface"""

    core_id: int = Field(description="LncRNA core ID")
    lncrna_gene_name: Optional[str] = Field(description="LncRNA gene symbol")
    lncrna_ensembl_id: Optional[str] = Field(default=None, description="LncRNA Ensembl ID")
    target_gene_name: Optional[str] = Field(description="Target gene symbol")
    target_ensembl_id: Optional[str] = Field(default=None, description="Target Ensembl ID")
    conservation_label: str = Field(description="Conservation pattern like '1111'")
    species_count: int = Field(description="Number of species where conserved")
    species_ids: List[int] = Field(description="List of species IDs where conserved")
    avg_binding_affinity: Optional[float] = Field(description="Average binding affinity across species")
    species_binding_affinities: List[SpeciesBindingAffinity] = Field(
        description="Binding affinity per species"
    )


class ConservedRegulationList(BaseModel):
    """Paginated list of conserved regulations"""

    items: List[ConservedRegulationItem]
    total: int
    page: int
    page_size: int
    total_pages: int

    # Filter info
    min_species: int = Field(description="Minimum species filter applied")

    model_config = ConfigDict(from_attributes=True)
