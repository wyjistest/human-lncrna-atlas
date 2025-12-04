"""API数据模型（Pydantic Schemas）"""

from .common import PaginationParams, PaginatedResponse
from .gene import (
    GeneBase,
    GeneDetail,
    GeneListItem,
    CoreGeneInfo,
    OrthologInfo,
)
from .regulation import (
    RegulationBase,
    RegulationDetail,
    RegulationListItem,
    RegulationFilter,
)
from .disease import (
    TraitBase,
    TraitDetail,
    TraitGeneAssociationDetail,
)
from .stats import (
    OverviewStats,
    SpeciesStats,
    GeneStats,
)
from .monitoring import (
    MetricsResponse,
    RequestMetrics,
    ErrorMetrics,
    ResponseTimeMetrics,
    HealthMetrics,
)
from .features import (
    FeatureTrackBase,
    FeatureTrackCreate,
    FeatureTrackResponse,
    GenomicFeatureBase,
    GenomicFeatureCreate,
    GenomicFeatureResponse,
    RepeatMaskerAttributes,
    RepeatMaskerFeature,
    RepeatMaskerResponse,
    RepeatStats,
    GeneRepeatSummary,
    FeatureTrackStats,
)

__all__ = [
    "PaginationParams",
    "PaginatedResponse",
    "GeneBase",
    "GeneDetail",
    "GeneListItem",
    "CoreGeneInfo",
    "OrthologInfo",
    "RegulationBase",
    "RegulationDetail",
    "RegulationListItem",
    "RegulationFilter",
    "TraitBase",
    "TraitDetail",
    "TraitGeneAssociationDetail",
    "OverviewStats",
    "SpeciesStats",
    "GeneStats",
    "MetricsResponse",
    "RequestMetrics",
    "ErrorMetrics",
    "ResponseTimeMetrics",
    "HealthMetrics",
    # Features
    "FeatureTrackBase",
    "FeatureTrackCreate",
    "FeatureTrackResponse",
    "GenomicFeatureBase",
    "GenomicFeatureCreate",
    "GenomicFeatureResponse",
    "RepeatMaskerAttributes",
    "RepeatMaskerFeature",
    "RepeatMaskerResponse",
    "RepeatStats",
    "GeneRepeatSummary",
    "FeatureTrackStats",
]
