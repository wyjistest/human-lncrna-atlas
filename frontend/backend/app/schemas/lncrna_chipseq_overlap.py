"""
lncRNA-ChIP-seq Overlap Analysis Schemas

Pydantic models for lncRNA binding site overlap with ChIP-seq peaks API
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from decimal import Decimal


class OverlapFilters(BaseModel):
    """Query parameters for lncRNA-ChIP-seq overlap analysis"""

    lncrna_gene_id: Optional[int] = Field(None, description="Filter by specific lncRNA gene ID")
    target_gene_id: Optional[int] = Field(None, description="Filter by specific target gene ID")
    mark_type: Optional[str] = Field(None, description="Filter by mark type(s), comma-separated (e.g., 'H3K27me3,H3K4me3')")
    cell_type: Optional[str] = Field(None, description="Filter by cell type(s), comma-separated (e.g., 'K562,GM12878')")
    chromosome: Optional[str] = Field(None, description="Filter by chromosome (e.g., 'chr1')")
    min_overlap_length: Optional[int] = Field(None, ge=1, description="Minimum overlap length in bp")
    min_binding_affinity: Optional[float] = Field(None, ge=0, description="Minimum binding affinity score")
    min_peak_strength: Optional[float] = Field(None, ge=0, description="Minimum peak fold enrichment")
    max_qvalue: Optional[float] = Field(0.05, ge=0, le=1, description="Maximum Q-value (FDR) for peaks")
    page: int = Field(1, ge=1, description="Page number (starts from 1)")
    page_size: int = Field(100, ge=1, le=1000, description="Items per page")
    sort_by: Optional[str] = Field("binding_affinity", description="Sort field (binding_affinity, overlap_length, peak_fold_enrichment)")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc or desc)")

    model_config = ConfigDict(from_attributes=True)


class OverlapResult(BaseModel):
    """Single overlap result between lncRNA binding site and ChIP-seq peak"""

    # Identifiers
    overlap_id: str = Field(..., description="Unique overlap identifier (format: reg_{regulation_id}_peak_{peak_id})")
    regulation_id: int = Field(..., description="Regulation record ID")

    # Gene information
    lncrna_gene_id: int = Field(..., description="lncRNA gene ID")
    lncrna_name: Optional[str] = Field(None, description="lncRNA gene name")
    target_gene_id: int = Field(..., description="Target gene ID")
    target_gene_name: Optional[str] = Field(None, description="Target gene name")

    # ChIP-seq experiment information
    mark_type: str = Field(..., description="Epigenetic mark type (e.g., H3K27me3)")
    mark_category: str = Field(..., description="Mark category (repressive, activating, etc.)")
    cell_type: str = Field(..., description="Cell type/line")

    # Genomic coordinates
    chromosome: str = Field(..., description="Chromosome")
    lncrna_binding_start: int = Field(..., description="lncRNA binding site start position")
    lncrna_binding_end: int = Field(..., description="lncRNA binding site end position")
    peak_start: int = Field(..., description="ChIP-seq peak start position")
    peak_end: int = Field(..., description="ChIP-seq peak end position")

    # Overlap region
    overlap_start: int = Field(..., description="Overlap region start position")
    overlap_end: int = Field(..., description="Overlap region end position")
    overlap_length: int = Field(..., description="Overlap length in bp")

    # Signal strength metrics
    binding_affinity: Decimal = Field(..., description="lncRNA binding affinity score")
    peak_fold_enrichment: Decimal = Field(..., description="ChIP-seq peak fold enrichment")
    peak_qvalue: Optional[Decimal] = Field(None, description="ChIP-seq peak Q-value (FDR)")

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: float}
    )


class OverlapResponse(BaseModel):
    """Paginated response for overlap query"""

    total: int = Field(..., description="Total number of matching overlaps")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    items: List[OverlapResult] = Field(default=[], description="List of overlap results")
    default_filter_applied: bool = Field(
        default=False,
        description="True if default chromosome filter (chr22) was applied for performance optimization"
    )
    effective_chromosome: Optional[str] = Field(
        default=None,
        description="The chromosome filter actually used in the query (may differ from requested if default was applied)"
    )
    using_materialized_view: bool = Field(
        default=False,
        description="True if the optimized materialized view was used for this query (faster for large chromosomes)"
    )

    model_config = ConfigDict(from_attributes=True)

    @staticmethod
    def calculate_total_pages(total: int, page_size: int) -> int:
        """Calculate total pages"""
        return (total + page_size - 1) // page_size if page_size > 0 else 0


class MarkTypeStats(BaseModel):
    """Statistics breakdown by mark type"""
    mark_type: str = Field(..., description="Epigenetic mark type name")
    count: int = Field(..., description="Number of overlaps for this mark type")
    avg_strength: float = Field(..., description="Average binding affinity for this mark type")

    model_config = ConfigDict(from_attributes=True)


class CellTypeStats(BaseModel):
    """Statistics breakdown by cell type"""
    cell_type: str = Field(..., description="Cell type/line name")
    count: int = Field(..., description="Number of overlaps for this cell type")

    model_config = ConfigDict(from_attributes=True)


class OverlapStatistics(BaseModel):
    """Summary statistics for overlap analysis"""

    total_overlaps: int = Field(..., description="Total number of overlaps")
    unique_lncrnas: int = Field(..., description="Number of unique lncRNAs")
    unique_target_genes: int = Field(..., description="Number of unique target genes")
    unique_marks: int = Field(..., description="Number of unique mark types")
    unique_cell_types: int = Field(default=0, description="Number of unique cell types")
    avg_overlap_length: float = Field(..., description="Average overlap length in bp")
    avg_binding_affinity: float = Field(..., description="Average binding affinity")
    avg_peak_strength: float = Field(..., description="Average peak fold enrichment")
    by_mark_type: List[MarkTypeStats] = Field(default=[], description="Statistics breakdown by mark type")
    by_cell_type: List[CellTypeStats] = Field(default=[], description="Statistics breakdown by cell type")
    default_filter_applied: bool = Field(
        default=False,
        description="True if default chromosome filter (chr22) was applied for performance optimization"
    )
    effective_chromosome: Optional[str] = Field(
        default=None,
        description="The chromosome filter actually used in the query (may differ from requested if default was applied)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: float}
    )


# ============================================================================
# Heatmap Schemas
# ============================================================================

class HeatmapCell(BaseModel):
    """Single cell in the heatmap matrix"""
    x: str = Field(..., description="X-axis value (mark_type or cell_type)")
    y: str = Field(..., description="Y-axis value (lncrna or target gene)")
    value: float = Field(..., description="Metric value for this cell")

    model_config = ConfigDict(from_attributes=True)


class OverlapHeatmapResponse(BaseModel):
    """Response schema for heatmap endpoint"""
    x_labels: List[str] = Field(..., description="List of X-axis labels")
    y_labels: List[str] = Field(..., description="List of Y-axis labels")
    data: List[HeatmapCell] = Field(..., description="Heatmap cell data")
    metric: str = Field(..., description="Metric used for values (count, avg_binding_affinity, total_overlap_length)")
    total_combinations: int = Field(..., description="Total possible X*Y combinations")
    valid_combinations: int = Field(..., description="Number of combinations with data")
    default_filter_applied: bool = Field(
        default=False,
        description="True if default chromosome filter (chr1) was applied for performance optimization"
    )
    effective_chromosome: Optional[str] = Field(
        default=None,
        description="The chromosome filter actually used in the query (may differ from requested if default was applied)"
    )

    model_config = ConfigDict(from_attributes=True)
