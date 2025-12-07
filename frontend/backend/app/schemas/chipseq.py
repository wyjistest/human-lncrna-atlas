"""
Pydantic Schemas for ChIP-seq Epigenetic Marks
Supports multiple histone modifications with unified architecture
"""
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime


# =============================================================================
# Enums for Type Safety
# =============================================================================

class MarkType(str, Enum):
    """Supported histone modification mark types"""
    # Repressive marks
    H3K27me3 = "H3K27me3"
    H3K9me3 = "H3K9me3"
    H4K20me3 = "H4K20me3"
    H3K9me2 = "H3K9me2"

    # Activating marks
    H3K4me1 = "H3K4me1"
    H3K4me3 = "H3K4me3"
    H3K27ac = "H3K27ac"
    H3K36me3 = "H3K36me3"
    H3K4me2 = "H3K4me2"
    H3K79me2 = "H3K79me2"
    H3K9ac = "H3K9ac"

    # Bivalent combination
    H3K4me3_H3K27me3 = "H3K4me3_H3K27me3"

    # Other/Structural
    H3K56ac = "H3K56ac"
    H2A_Z = "H2A.Z"
    CTCF = "CTCF"


class MarkCategory(str, Enum):
    """Categories of epigenetic marks"""
    repressive = "repressive"
    activating = "activating"
    bivalent_component = "bivalent_component"
    structural = "structural"
    other = "other"


class OverlapType(str, Enum):
    """Types of peak-gene overlap"""
    promoter = "promoter"
    gene_body = "gene_body"
    tss = "tss"
    tes = "tes"
    upstream = "upstream"
    downstream = "downstream"
    intergenic = "intergenic"
    overlapping = "overlapping"


class RelationshipType(str, Enum):
    """Types of relationships between marks"""
    bivalent_pair = "bivalent_pair"
    antagonistic = "antagonistic"
    synergistic = "synergistic"
    co_occurring = "co_occurring"
    mutually_exclusive = "mutually_exclusive"


# =============================================================================
# Mark Type Schemas
# =============================================================================

class EpigeneticMarkTypeBase(BaseModel):
    """Base schema for epigenetic mark types"""
    mark_name: str = Field(..., max_length=50, description="Mark identifier (e.g., H3K27me3)")
    mark_category: MarkCategory = Field(..., description="Mark functional category")
    display_name: str = Field(..., max_length=100, description="Human-readable display name")
    display_color: Optional[str] = Field("#666666", max_length=20, description="Hex color for visualization")
    biological_function: Optional[str] = Field(None, description="Brief biological description")
    associated_state: Optional[str] = Field(None, max_length=100, description="Associated chromatin state")


class EpigeneticMarkTypeResponse(EpigeneticMarkTypeBase):
    """Response schema for epigenetic mark types"""
    mark_type_id: int
    description: Optional[str] = None
    typical_signal_range: Optional[Dict[str, Any]] = None
    is_active: bool = True
    sort_order: int = 100

    model_config = ConfigDict(from_attributes=True)


class MarkRelationshipResponse(BaseModel):
    """Response schema for mark relationships"""
    relationship_id: int
    mark_1: str = Field(..., description="First mark name")
    mark_2: str = Field(..., description="Second mark name")
    relationship_type: RelationshipType
    description: Optional[str] = None
    biological_significance: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Experiment Schemas
# =============================================================================

class ChIPSeqExperimentBase(BaseModel):
    """Base schema for ChIP-seq experiments"""
    experiment_name: str = Field(..., max_length=200, description="Unique experiment name")
    cell_type: Optional[str] = Field(None, max_length=200, description="Cell type (e.g., H1-hESC)")
    tissue_type: Optional[str] = Field(None, max_length=200, description="Tissue type (e.g., brain)")
    cell_line: Optional[str] = Field(None, max_length=200, description="Specific cell line")
    treatment: Optional[str] = Field(None, max_length=200, description="Experimental treatment")


class ChIPSeqExperimentCreate(ChIPSeqExperimentBase):
    """Schema for creating ChIP-seq experiments"""
    species_id: int = Field(..., description="Species ID")
    mark_type: str = Field(..., description="Mark type name (e.g., H3K27me3)")

    # Data source
    source_database: Optional[str] = Field(None, max_length=100, description="Data source (ENCODE, GEO)")
    source_accession: Optional[str] = Field(None, max_length=100, description="Accession number")
    data_url: Optional[str] = Field(None, description="Direct link to raw data")

    # Processing info
    pipeline_version: Optional[str] = Field(None, max_length=50)
    peak_caller: Optional[str] = Field("MACS2", max_length=50)
    peak_caller_version: Optional[str] = Field(None, max_length=50)
    reference_genome: Optional[str] = Field(None, max_length=50, description="e.g., GRCh38")

    # Quality metrics
    total_reads: Optional[int] = Field(None, ge=0)
    mapped_reads: Optional[int] = Field(None, ge=0)
    duplicate_rate: Optional[float] = Field(None, ge=0, le=1)
    frip_score: Optional[float] = Field(None, ge=0, le=1, description="Fraction of Reads in Peaks")

    # Thresholds
    signal_threshold: Optional[Dict[str, Any]] = Field(
        None,
        description="Signal thresholds (e.g., qvalue_cutoff, fold_enrichment_min)"
    )

    # Flexible config
    mark_specific_config: Optional[Dict[str, Any]] = Field(None, description="Mark-specific parameters")


class ChIPSeqExperimentResponse(ChIPSeqExperimentBase):
    """Response schema for ChIP-seq experiments"""
    experiment_id: int
    species_id: int
    species_code: Optional[str] = None  # Joined from species table

    # Mark info
    mark_type: str
    mark_category: str
    mark_display_color: Optional[str] = None

    # Data source
    source_database: Optional[str] = None
    source_accession: Optional[str] = None

    # Processing info
    peak_caller: Optional[str] = None
    reference_genome: Optional[str] = None

    # Quality metrics
    total_reads: Optional[int] = None
    mapped_reads: Optional[int] = None
    frip_score: Optional[float] = None

    # Status
    is_active: bool = True
    created_at: datetime

    # Stats (joined from peaks)
    peak_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ChIPSeqExperimentListResponse(BaseModel):
    """Paginated list of experiments"""
    total: int = Field(..., description="Total matching experiments")
    items: List[ChIPSeqExperimentResponse]
    page: int = 1
    page_size: int = 20


# =============================================================================
# Peak Schemas
# =============================================================================

class ChIPSeqPeakBase(BaseModel):
    """Base schema for ChIP-seq peaks"""
    chromosome: str = Field(..., max_length=20, description="Chromosome name")
    peak_start: int = Field(..., ge=0, description="Peak start position (0-based)")
    peak_end: int = Field(..., gt=0, description="Peak end position")
    summit_position: Optional[int] = Field(None, description="Summit position within peak")

    @field_validator('peak_end')
    @classmethod
    def validate_end_greater_than_start(cls, v, info):
        if 'peak_start' in info.data and v <= info.data['peak_start']:
            raise ValueError('peak_end must be greater than peak_start')
        return v


class ChIPSeqPeakCreate(ChIPSeqPeakBase):
    """Schema for creating ChIP-seq peaks"""
    experiment_id: int = Field(..., description="Experiment ID")
    species_id: int = Field(..., description="Species ID")

    peak_name: Optional[str] = Field(None, max_length=200, description="Original peak name")
    strand: Optional[str] = Field(".", pattern=r'^[\+\-\.]$')

    # Signal metrics
    fold_enrichment: Optional[float] = Field(None, ge=0, description="Fold enrichment over background")
    pvalue: Optional[float] = Field(None, ge=0, le=1, description="Raw p-value")
    qvalue: Optional[float] = Field(None, ge=0, le=1, description="FDR-corrected q-value")
    signal_value: Optional[float] = Field(None, description="Normalized signal value")
    score: Optional[int] = Field(None, ge=0, le=1000, description="BED score (0-1000)")

    # Additional attributes
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChIPSeqPeak(ChIPSeqPeakBase):
    """Full peak response schema with all fields"""
    peak_id: int
    experiment_id: int

    peak_name: Optional[str] = None
    strand: str = "."

    # Signal metrics
    fold_enrichment: Optional[float] = None
    log2_fold_enrichment: Optional[float] = None
    pvalue: Optional[float] = None
    neg_log10_pvalue: Optional[float] = None
    qvalue: Optional[float] = None
    neg_log10_qvalue: Optional[float] = None
    signal_value: Optional[float] = None
    score: Optional[int] = None

    # Computed
    peak_width: int

    # Mark info (from joined experiment)
    mark_type: Optional[str] = None
    mark_category: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_db_row(cls, row, mark_type: str = None, mark_category: str = None) -> "ChIPSeqPeak":
        """Convert database row to Pydantic model"""
        return cls(
            peak_id=row.peak_id,
            experiment_id=row.experiment_id,
            chromosome=row.chromosome,
            peak_start=row.peak_start,
            peak_end=row.peak_end,
            summit_position=row.summit_position,
            peak_name=row.peak_name,
            strand=row.strand or ".",
            fold_enrichment=float(row.fold_enrichment) if row.fold_enrichment else None,
            log2_fold_enrichment=float(row.log2_fold_enrichment) if row.log2_fold_enrichment else None,
            pvalue=float(row.pvalue) if row.pvalue else None,
            neg_log10_pvalue=float(row.neg_log10_pvalue) if row.neg_log10_pvalue else None,
            qvalue=float(row.qvalue) if row.qvalue else None,
            neg_log10_qvalue=float(row.neg_log10_qvalue) if row.neg_log10_qvalue else None,
            signal_value=float(row.signal_value) if row.signal_value else None,
            score=row.score,
            peak_width=row.peak_width or (row.peak_end - row.peak_start),
            mark_type=mark_type,
            mark_category=mark_category,
        )


class ChIPSeqPeakCompact(BaseModel):
    """Compact peak schema for list responses"""
    peak_id: int
    chromosome: str
    start: int = Field(..., alias="peak_start")
    end: int = Field(..., alias="peak_end")
    summit: Optional[int] = Field(None, alias="summit_position")
    fold_enrichment: Optional[float] = None
    qvalue: Optional[float] = None
    mark_type: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# =============================================================================
# Gene-Peak Association Schemas
# =============================================================================

class GenePeakAssociation(BaseModel):
    """Peak associated with a gene"""
    peak_id: int
    chromosome: str
    peak_start: int
    peak_end: int
    summit_position: Optional[int] = None

    # Association info
    overlap_type: OverlapType
    distance_to_tss: Optional[int] = None
    overlap_bp: Optional[int] = None

    # Signal
    fold_enrichment: Optional[float] = None
    qvalue: Optional[float] = None

    # Mark info
    mark_type: str
    mark_category: str
    experiment_id: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Response Schemas
# =============================================================================

class ChIPSeqPaginatedResponse(BaseModel):
    """Paginated response for ChIP-seq peaks"""
    total: int = Field(..., description="Total matching peaks")
    items: List[ChIPSeqPeak]
    page: int = 1
    page_size: int = 50

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0


class GeneChIPSeqResponse(BaseModel):
    """ChIP-seq data for a specific gene"""
    gene_id: int
    gene_name: str
    chromosome: str
    gene_start: int
    gene_end: int
    strand: str
    region_start: int = Field(..., description="Query region start (gene - flanking)")
    region_end: int = Field(..., description="Query region end (gene + flanking)")

    # Peak data grouped by mark type
    marks: Dict[str, List[GenePeakAssociation]] = Field(
        ...,
        description="Peaks grouped by mark type"
    )

    # Summary statistics
    total_peaks: int
    marks_present: List[str] = Field(..., description="List of mark types with peaks")


class MarkSummaryStats(BaseModel):
    """Summary statistics for a mark type in a gene region"""
    mark_type: str
    mark_category: str
    peak_count: int
    max_fold_enrichment: Optional[float] = None
    avg_fold_enrichment: Optional[float] = None
    best_qvalue: Optional[float] = None
    total_peak_coverage_bp: int = 0
    overlap_types: List[str] = []


class GeneChIPSeqSummary(BaseModel):
    """Summary of ChIP-seq marks for a gene"""
    gene_id: int
    gene_name: str
    chromosome: str
    gene_start: int
    gene_end: int
    region_start: int
    region_end: int
    region_length: int

    # Per-mark statistics
    mark_summaries: List[MarkSummaryStats]

    # Overall stats
    total_marks: int = Field(..., description="Number of distinct marks with peaks")
    total_peaks: int = Field(..., description="Total peaks across all marks")

    # Bivalent detection
    has_bivalent_domain: bool = Field(
        False,
        description="True if both H3K4me3 and H3K27me3 present"
    )


# =============================================================================
# Comparison Schemas
# =============================================================================

class PeakWidthPercentiles(BaseModel):
    """Peak width percentile distribution"""
    p25: Optional[float] = Field(None, description="25th percentile of peak widths")
    p50: Optional[float] = Field(None, description="50th percentile (median) of peak widths")
    p75: Optional[float] = Field(None, description="75th percentile of peak widths")


class MarkComparisonEntry(BaseModel):
    """Single mark entry in comparison with enhanced statistics"""
    mark_type: str
    mark_category: str
    display_color: str
    peaks: List[ChIPSeqPeakCompact]
    peak_count: int

    # Basic statistics
    avg_fold_enrichment: Optional[float] = Field(None, description="Mean fold enrichment")

    # Enhanced statistics (Phase 2.5)
    median_fold_enrichment: Optional[float] = Field(None, description="Median fold enrichment")
    std_fold_enrichment: Optional[float] = Field(None, description="Standard deviation of fold enrichment")
    total_coverage_bp: Optional[int] = Field(None, description="Total base pairs covered by all peaks")
    peak_width_percentiles: Optional[PeakWidthPercentiles] = Field(
        None,
        description="Peak width distribution (p25, p50, p75)"
    )


class OverlapRegion(BaseModel):
    """Overlap region between two marks"""
    chromosome: str
    start: int
    end: int
    length: int = Field(..., description="Overlap length in bp")
    mark_1: str = Field(..., description="First mark name")
    mark_2: str = Field(..., description="Second mark name")
    mark_1_peak_id: int = Field(..., description="Peak ID from first mark")
    mark_2_peak_id: int = Field(..., description="Peak ID from second mark")
    overlap_type: Optional[str] = Field(None, description="Type of overlap (e.g., bivalent, antagonistic)")


class OverlapStatistics(BaseModel):
    """Summary statistics for mark overlaps"""
    mark_pair: str = Field(..., description="Mark pair (e.g., 'H3K4me3:H3K27me3')")
    overlap_count: int = Field(..., description="Number of overlapping regions")
    total_overlap_bp: int = Field(..., description="Total base pairs in overlaps")
    avg_overlap_length: Optional[float] = Field(None, description="Average overlap length")
    is_bivalent: bool = Field(False, description="Whether this is a bivalent pair")


class ChIPSeqComparisonResponse(BaseModel):
    """Response for comparing multiple marks with enhanced overlap analysis"""
    gene_id: int
    gene_name: str
    chromosome: str
    region_start: int
    region_end: int

    # Marks being compared
    marks: List[MarkComparisonEntry]

    # Generalized overlap analysis (Phase 2.5)
    all_overlaps: Optional[List[OverlapRegion]] = Field(
        None,
        description="All pairwise overlapping regions between marks"
    )
    overlap_statistics: Optional[List[OverlapStatistics]] = Field(
        None,
        description="Summary statistics for each mark pair overlap"
    )

    # Legacy fields for backward compatibility
    overlapping_regions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="[Deprecated] Use all_overlaps instead"
    )
    bivalent_regions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Regions with H3K4me3 + H3K27me3 co-occurrence (bivalent domains)"
    )


# =============================================================================
# Statistics Schemas
# =============================================================================

class ChIPSeqMarkStats(BaseModel):
    """Statistics for a mark type"""
    mark_name: str
    mark_category: str
    display_color: str
    species_code: str
    experiment_count: int
    total_peaks: int
    avg_fold_enrichment: Optional[float] = None
    median_fold_enrichment: Optional[float] = None
    avg_peak_width: Optional[float] = None


class ChIPSeqGlobalStats(BaseModel):
    """Global ChIP-seq statistics"""
    total_experiments: int
    total_peaks: int
    marks_available: List[str]
    species_available: List[str]
    stats_by_mark: List[ChIPSeqMarkStats]


# =============================================================================
# Bulk Import Schemas
# =============================================================================

class ChIPSeqPeakBulkCreate(BaseModel):
    """Schema for bulk peak import"""
    experiment_id: int = Field(..., description="Experiment ID to associate peaks with")
    peaks: List[ChIPSeqPeakCreate] = Field(..., description="List of peaks to import")


class ChIPSeqBulkImportResponse(BaseModel):
    """Response for bulk import operations"""
    success: bool
    experiment_id: int
    peaks_imported: int
    peaks_skipped: int
    errors: List[str] = []
    message: str


# =============================================================================
# Query/Filter Schemas
# =============================================================================

class ChIPSeqQueryParams(BaseModel):
    """Query parameters for ChIP-seq endpoints"""
    mark_type: Optional[List[str]] = Field(
        None,
        description="Filter by mark type(s). Multiple values supported."
    )
    mark_category: Optional[MarkCategory] = Field(
        None,
        description="Filter by mark category"
    )
    experiment_id: Optional[int] = Field(
        None,
        description="Filter by specific experiment"
    )
    min_fold_enrichment: Optional[float] = Field(
        None,
        ge=0,
        description="Minimum fold enrichment threshold"
    )
    max_qvalue: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Maximum q-value threshold"
    )
    cell_type: Optional[str] = Field(
        None,
        description="Filter by cell type"
    )


class RegionQueryParams(BaseModel):
    """Query parameters for region-based queries"""
    chromosome: str = Field(..., description="Chromosome name")
    start: int = Field(..., ge=0, description="Region start")
    end: int = Field(..., ge=0, description="Region end")

    @model_validator(mode='after')
    def validate_region(self) -> 'RegionQueryParams':
        if self.end <= self.start:
            raise ValueError('end must be greater than start')
        return self


# =============================================================================
# Available Marks Response
# =============================================================================

class AvailableMarksResponse(BaseModel):
    """List of available marks for a species"""
    species_id: int
    species_code: str
    marks: List[EpigeneticMarkTypeResponse]
    total_experiments: int
    total_peaks: int


# =============================================================================
# Export Schemas (Phase 2.5)
# =============================================================================

class ExportFormat(str, Enum):
    """Supported export formats"""
    csv = "csv"
    tsv = "tsv"
    bed = "bed"
    json = "json"


class ComparisonExportRequest(BaseModel):
    """Request parameters for comparison export"""
    marks: List[str] = Field(..., description="Mark types to include")
    include_overlaps: bool = Field(True, description="Include overlap regions")
    include_statistics: bool = Field(True, description="Include statistics")


class OverlapExportRequest(BaseModel):
    """Request parameters for overlap export"""
    mark_pair: Optional[str] = Field(
        None,
        description="Specific mark pair to export (e.g., 'H3K4me3:H3K27me3'). If None, export all."
    )
    min_overlap_bp: int = Field(0, ge=0, description="Minimum overlap length to include")


# =============================================================================
# Cell Line Comparison Schemas (Cross Cell-Line Analysis)
# =============================================================================

class CellLineComparisonEntry(BaseModel):
    """Single cell line data in comparison for a specific mark"""
    cell_type: str = Field(..., description="Cell type identifier (e.g., K562, HepG2)")
    cell_line: Optional[str] = Field(None, description="Specific cell line name if available")
    peaks: List[ChIPSeqPeakCompact] = Field(..., description="Peaks from this cell line")

    # Statistics
    total_peaks: int = Field(..., description="Total number of peaks")
    avg_signal: Optional[float] = Field(None, description="Average signal value")
    median_fold_enrichment: Optional[float] = Field(None, description="Median fold enrichment")
    std_fold_enrichment: Optional[float] = Field(None, description="Standard deviation of fold enrichment")
    total_coverage_bp: int = Field(..., description="Total base pairs covered by peaks")
    peak_width_percentiles: Optional[PeakWidthPercentiles] = Field(
        None,
        description="Peak width distribution (p25, p50, p75)"
    )


class CellLineOverlapRegion(BaseModel):
    """Overlap between two cell lines for the same mark"""
    chromosome: str = Field(..., description="Chromosome name")
    start: int = Field(..., description="Overlap start position")
    end: int = Field(..., description="Overlap end position")
    length: int = Field(..., description="Overlap length in bp")
    cell_type_1: str = Field(..., description="First cell type")
    cell_type_2: str = Field(..., description="Second cell type")
    peak_id_1: int = Field(..., description="Peak ID from first cell type")
    peak_id_2: int = Field(..., description="Peak ID from second cell type")


class CellLineOverlapStatistics(BaseModel):
    """Summary statistics for cell line overlaps"""
    cell_pair: str = Field(..., description="Cell type pair (e.g., 'K562:HepG2')")
    overlap_count: int = Field(..., description="Number of overlapping regions")
    total_overlap_bp: int = Field(..., description="Total base pairs in overlaps")
    avg_overlap_length: Optional[float] = Field(None, description="Average overlap length")
    jaccard_index: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Jaccard similarity index between peak sets"
    )


class CellLineComparisonResponse(BaseModel):
    """Response for comparing same mark across multiple cell lines"""
    gene_id: int = Field(..., description="Gene ID")
    gene_name: str = Field(..., description="Gene symbol or name")
    gene_ensembl_id: str = Field(..., description="Ensembl gene ID")
    chromosome: str = Field(..., description="Chromosome")
    region_start: int = Field(..., description="Query region start (gene - flanking)")
    region_end: int = Field(..., description="Query region end (gene + flanking)")
    mark_type: str = Field(..., description="Single mark being compared across cell lines")

    # Cell line data
    cell_lines: List[CellLineComparisonEntry] = Field(
        ...,
        description="Peak data for each cell line"
    )

    # Overlap analysis
    overlap_regions: Optional[List[CellLineOverlapRegion]] = Field(
        None,
        description="All pairwise overlapping regions between cell lines"
    )
    overlap_statistics: Optional[List[CellLineOverlapStatistics]] = Field(
        None,
        description="Summary statistics for each cell line pair"
    )

    # Summary
    total_cell_lines: int = Field(..., description="Number of cell lines with data")
    common_peaks: int = Field(
        ...,
        description="Peaks present in all cell lines (based on overlap)"
    )

    # Missing cell lines (requested but no data found)
    missing_cell_lines: Optional[List[str]] = Field(
        None,
        description="Cell types requested but not found in data"
    )


# =============================================================================
# Heatmap Matrix Schemas (Multi-Cell-Line x Multi-Mark Analysis)
# =============================================================================

class CellMarkStats(BaseModel):
    """Statistics for a single cell_type x mark combination"""
    median_fold_enrichment: Optional[float] = Field(
        None,
        description="Median fold enrichment value"
    )
    peak_count: int = Field(
        0,
        description="Number of peaks"
    )
    total_coverage_bp: int = Field(
        0,
        description="Total base pairs covered by peaks"
    )
    avg_signal: Optional[float] = Field(
        None,
        description="Average signal value"
    )
    std_fold_enrichment: Optional[float] = Field(
        None,
        description="Standard deviation of fold enrichment"
    )


class HeatmapMatrixResponse(BaseModel):
    """
    Response for heatmap matrix - multiple cell lines x multiple marks.
    Optimized for ECharts heatmap visualization.
    """
    # Gene information
    gene_id: int = Field(..., description="Gene ID")
    gene_name: str = Field(..., description="Gene symbol or name")
    gene_ensembl_id: str = Field(..., description="Ensembl gene ID")
    chromosome: str = Field(..., description="Chromosome")
    region_start: int = Field(..., description="Query region start (gene - flanking)")
    region_end: int = Field(..., description="Query region end (gene + flanking)")

    # Matrix dimensions
    cell_types: List[str] = Field(
        ...,
        description="Y-axis: ordered list of cell types"
    )
    marks: List[str] = Field(
        ...,
        description="X-axis: ordered list of marks"
    )
    metric: str = Field(
        ...,
        description="Metric used for matrix values (e.g., median_fold_enrichment)"
    )

    # Core matrix data
    # matrix[y][x] = cell_types[y] x marks[x] metric value
    # None indicates no data for that combination
    matrix: List[List[Optional[float]]] = Field(
        ...,
        description="2D matrix, matrix[cell_type_index][mark_index]"
    )

    # Optional: detailed statistics for rich tooltips
    details: Optional[Dict[str, Dict[str, CellMarkStats]]] = Field(
        None,
        description="Detailed stats: details[cell_type][mark]"
    )

    # Metadata
    missing_combinations: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of missing cell_type-mark combinations"
    )
    total_combinations: int = Field(
        ...,
        description="Total number of cell_type x mark combinations"
    )
    valid_combinations: int = Field(
        ...,
        description="Number of combinations with valid data"
    )
