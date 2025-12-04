"""
Pydantic Schemas for Genomic Features (RepeatMasker, etc.)
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime


# =============================================================================
# Feature Track Schemas
# =============================================================================

class FeatureTrackBase(BaseModel):
    """Base schema for feature tracks"""
    track_name: str = Field(..., max_length=100, description="Unique track identifier")
    track_category: str = Field(..., max_length=50, description="Track category (repeat, epigenetic, conservation)")
    display_name: str = Field(..., max_length=200, description="Human-readable display name")
    display_color: Optional[str] = Field(None, max_length=20, description="Display color (hex code)")
    source_database: Optional[str] = Field(None, max_length=100, description="Data source database")
    version: Optional[str] = Field(None, max_length=50, description="Data version")
    is_active: bool = Field(default=True, description="Whether the track is active")


class FeatureTrackCreate(FeatureTrackBase):
    """Schema for creating a feature track"""
    attribute_schema: Optional[Dict[str, Any]] = Field(None, description="JSON Schema for attribute validation")


class FeatureTrackResponse(FeatureTrackBase):
    """Schema for feature track response"""
    track_id: int
    attribute_schema: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Generic Genomic Feature Schemas
# =============================================================================

class GenomicFeatureBase(BaseModel):
    """Base schema for genomic features"""
    chromosome: str = Field(..., max_length=20, description="Chromosome name")
    feature_start: int = Field(..., ge=0, description="Start position (0-based)")
    feature_end: int = Field(..., gt=0, description="End position")
    feature_name: Optional[str] = Field(None, max_length=200, description="Feature name")
    strand: Optional[str] = Field(None, pattern=r'^[\+\-\.]$', description="Strand (+/-/.)")
    score: Optional[float] = Field(None, description="Score value")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Track-specific attributes")

    @field_validator('feature_end')
    @classmethod
    def validate_end_greater_than_start(cls, v, info):
        if 'feature_start' in info.data and v <= info.data['feature_start']:
            raise ValueError('feature_end must be greater than feature_start')
        return v


class GenomicFeatureCreate(GenomicFeatureBase):
    """Schema for creating a genomic feature"""
    track_id: int = Field(..., description="Track ID")
    species_id: int = Field(..., description="Species ID")
    batch_id: Optional[int] = Field(None, description="Import batch ID")


class GenomicFeatureResponse(GenomicFeatureBase):
    """Schema for genomic feature response"""
    feature_id: int
    track_id: int
    species_id: int
    batch_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# RepeatMasker Specific Schemas
# =============================================================================

class RepeatMaskerAttributes(BaseModel):
    """RepeatMasker-specific attributes"""
    repeat_class: str = Field(..., description="Repeat class (LINE, SINE, LTR, DNA, etc.)")
    repeat_family: str = Field(..., description="Repeat family (L1, Alu, etc.)")
    divergence: float = Field(..., ge=0, le=100, description="Percent divergence from consensus (0-100)")


class RepeatMaskerFeature(BaseModel):
    """Flattened RepeatMasker feature for API response"""
    feature_id: int = Field(..., description="Unique feature ID")
    chromosome: str = Field(..., description="Chromosome name")
    start: int = Field(..., description="Start position")
    end: int = Field(..., description="End position")
    repeat_name: str = Field(..., description="Repeat element name")
    repeat_class: str = Field(..., description="Repeat class (LINE, SINE, LTR, DNA, etc.)")
    repeat_family: str = Field(..., description="Repeat family (L1, Alu, etc.)")
    divergence: float = Field(..., description="Percent divergence from consensus")
    strand: Optional[str] = Field(None, description="Strand (+/-/.)")
    score: Optional[float] = Field(None, description="Score value")

    @classmethod
    def from_genomic_feature(cls, feature) -> "RepeatMaskerFeature":
        """Convert a GenomicFeature ORM object to RepeatMaskerFeature"""
        attrs = feature.attributes or {}
        return cls(
            feature_id=feature.feature_id,
            chromosome=feature.chromosome,
            start=feature.feature_start,
            end=feature.feature_end,
            repeat_name=feature.feature_name or "Unknown",
            repeat_class=attrs.get('repeat_class', 'Unknown'),
            repeat_family=attrs.get('repeat_family', 'Unknown'),
            divergence=float(attrs.get('divergence', 0.0)),
            strand=feature.strand,
            score=float(feature.score) if feature.score is not None else None,
        )

    model_config = ConfigDict(from_attributes=True)


class RepeatMaskerResponse(BaseModel):
    """Paginated response for RepeatMasker features"""
    total: int = Field(..., description="Total number of features matching the query")
    items: List[RepeatMaskerFeature] = Field(..., description="List of RepeatMasker features")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")

    @property
    def total_pages(self) -> int:
        """Calculate total pages"""
        return (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0


# =============================================================================
# Statistics Schemas
# =============================================================================

class RepeatClassDistribution(BaseModel):
    """Distribution of repeat classes"""
    repeat_class: str = Field(..., description="Repeat class name")
    count: int = Field(..., description="Number of features in this class")
    percentage: float = Field(..., description="Percentage of total")


class RepeatFamilyDistribution(BaseModel):
    """Distribution of repeat families"""
    repeat_family: str = Field(..., description="Repeat family name")
    repeat_class: str = Field(..., description="Parent repeat class")
    count: int = Field(..., description="Number of features in this family")
    percentage: float = Field(..., description="Percentage of total")


class RepeatStats(BaseModel):
    """RepeatMasker statistics for a gene region"""
    total_count: int = Field(..., description="Total number of repeat elements")
    total_length: int = Field(..., description="Total length covered by repeats (bp)")
    coverage_percentage: float = Field(..., description="Percentage of region covered by repeats")
    class_distribution: List[RepeatClassDistribution] = Field(..., description="Distribution by repeat class")
    family_distribution: List[RepeatFamilyDistribution] = Field(..., description="Distribution by repeat family (top 10)")
    avg_divergence: float = Field(..., description="Average percent divergence")
    min_divergence: float = Field(..., description="Minimum percent divergence")
    max_divergence: float = Field(..., description="Maximum percent divergence")


class GeneRepeatSummary(BaseModel):
    """Summary of repeat elements for a gene"""
    gene_id: int = Field(..., description="Gene ID")
    gene_name: str = Field(..., description="Gene name")
    chromosome: str = Field(..., description="Chromosome")
    gene_start: int = Field(..., description="Gene start position")
    gene_end: int = Field(..., description="Gene end position")
    region_start: int = Field(..., description="Query region start (gene +/- flanking)")
    region_end: int = Field(..., description="Query region end (gene +/- flanking)")
    stats: RepeatStats = Field(..., description="Repeat statistics")


# =============================================================================
# Feature Track Statistics
# =============================================================================

class FeatureTrackStats(BaseModel):
    """Statistics for a feature track"""
    track_id: int = Field(..., description="Track ID")
    track_name: str = Field(..., description="Track name")
    display_name: str = Field(..., description="Display name")
    species_stats: Dict[str, int] = Field(..., description="Feature count by species")
    total_features: int = Field(..., description="Total feature count across all species")


# =============================================================================
# Bulk Import Schemas
# =============================================================================

class RepeatMaskerBulkCreate(BaseModel):
    """Schema for bulk creating RepeatMasker features"""
    species_id: int = Field(..., description="Species ID")
    features: List[GenomicFeatureCreate] = Field(..., description="List of features to create")
    batch_name: Optional[str] = Field(None, description="Import batch name")


class BulkImportResponse(BaseModel):
    """Response for bulk import operations"""
    success: bool = Field(..., description="Whether the import was successful")
    batch_id: int = Field(..., description="Import batch ID")
    total_imported: int = Field(..., description="Number of features imported")
    total_skipped: int = Field(..., description="Number of features skipped")
    message: str = Field(..., description="Status message")
