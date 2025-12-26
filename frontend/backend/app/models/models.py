"""
SQLAlchemy ORM 模型
映射数据库表结构
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now():
    """返回当前 UTC 时间（兼容 Python 3.12+，避免弃用的 utcnow()）"""
    return datetime.now(timezone.utc)


class Species(Base):
    """物种表"""

    __tablename__ = "species"

    species_id = Column(Integer, primary_key=True, autoincrement=True)
    species_code = Column(String(20), nullable=False, unique=True)
    display_name = Column(String(100))
    latin_name = Column(String(100))
    genome_assembly = Column(String(50))
    created_at = Column(DateTime, default=utc_now)

    # 关系
    genes = relationship("Gene", back_populates="species")
    regulations = relationship("Regulation", back_populates="species")


class CoreGene(Base):
    """核心基因表（跨物种唯一标识）"""

    __tablename__ = "core_genes"

    core_id = Column(Integer, primary_key=True)
    gene_type = Column(String(20), nullable=False)
    canonical_symbol = Column(String(100))
    human_ensembl_id = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    # 关系
    genes = relationship("Gene", back_populates="core_gene")
    trait_associations = relationship("TraitGeneAssociation", back_populates="core_gene")

    __table_args__ = (
        CheckConstraint("gene_type IN ('lncRNA', 'protein_coding')", name="core_genes_gene_type_check"),
    )


class Gene(Base):
    """基因表（物种特异性）"""

    __tablename__ = "genes"

    gene_id = Column(Integer, primary_key=True, autoincrement=True)
    # Note: core_id can be NULL for genes without ortholog information
    # Schema comment: "关联到core_genes，NULL表示该基因无同源信息"
    core_id = Column(Integer, ForeignKey("core_genes.core_id"), nullable=True)
    species_id = Column(Integer, ForeignKey("species.species_id"), nullable=False)
    gene_ensembl_id = Column(String(50), nullable=False)
    gene_name = Column(String(100))
    chromosome = Column(String(20))
    gene_start = Column(BigInteger)
    gene_end = Column(BigInteger)
    strand = Column(String(1))
    created_at = Column(DateTime, default=utc_now)

    # 关系
    core_gene = relationship("CoreGene", back_populates="genes")
    species = relationship("Species", back_populates="genes")
    regulations_as_lncrna = relationship(
        "Regulation",
        foreign_keys="Regulation.lncrna_gene_id",
        back_populates="lncrna_gene",
    )
    regulations_as_target = relationship(
        "Regulation",
        foreign_keys="Regulation.target_gene_id",
        back_populates="target_gene",
    )

    __table_args__ = (
        UniqueConstraint("species_id", "gene_ensembl_id", name="genes_species_id_gene_ensembl_id_key"),
        CheckConstraint("gene_end > gene_start", name="genes_check"),
        CheckConstraint("gene_start >= 0", name="genes_gene_start_check"),
        CheckConstraint("strand IN ('+', '-', '.')", name="genes_strand_check"),
    )


class ImportBatch(Base):
    """导入批次表"""

    __tablename__ = "import_batches"

    batch_id = Column(Integer, primary_key=True, autoincrement=True)
    batch_name = Column(String(200), nullable=False)
    batch_type = Column(String(50))
    species_id = Column(Integer, ForeignKey("species.species_id"))
    import_date = Column(DateTime, default=utc_now)
    source_file = Column(String(500))
    record_count = Column(BigInteger)
    status = Column(String(20), default="in_progress")
    error_message = Column(Text)
    completed_at = Column(DateTime)

    # 关系
    regulations = relationship("Regulation", back_populates="batch")

    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed', 'failed')", name="import_batches_status_check"),
    )


class Regulation(Base):
    """调控关系表"""

    __tablename__ = "regulations"

    regulation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("import_batches.batch_id"))
    species_id = Column(Integer, ForeignKey("species.species_id"), nullable=False)
    lncrna_gene_id = Column(Integer, ForeignKey("genes.gene_id"), nullable=False)
    target_gene_id = Column(Integer, ForeignKey("genes.gene_id"), nullable=False)
    target_chromosome = Column(String(50))
    target_start = Column(BigInteger)
    target_end = Column(BigInteger)
    tfo_file = Column(String(500))
    total_sites = Column(Integer)
    kept_sites = Column(Integer)
    num_peaks = Column(Integer)
    best_peak_num = Column(Integer)
    best_avg_ba = Column(Numeric(10, 4))
    best_num_sites = Column(Integer)
    best_peak_chr = Column(String(50))
    best_peak_start = Column(BigInteger)
    best_peak_end = Column(BigInteger)
    best_site_ba = Column(Numeric(10, 4))
    lncrna_start = Column(Integer)  # Matches database schema (integer type)
    lncrna_end = Column(Integer)    # Matches database schema (integer type)
    dna_start = Column(BigInteger)
    dna_end = Column(BigInteger)
    binding_affinity = Column(Numeric(10, 4))
    created_at = Column(DateTime, default=utc_now)

    # 关系
    batch = relationship("ImportBatch", back_populates="regulations")
    species = relationship("Species", back_populates="regulations")
    lncrna_gene = relationship(
        "Gene",
        foreign_keys=[lncrna_gene_id],
        back_populates="regulations_as_lncrna",
    )
    target_gene = relationship(
        "Gene",
        foreign_keys=[target_gene_id],
        back_populates="regulations_as_target",
    )
    sequence = relationship("Sequence", back_populates="regulation", uselist=False)

    __table_args__ = (
        CheckConstraint("target_end > target_start", name="regulations_check"),
        CheckConstraint("target_start >= 0", name="regulations_target_start_check"),
        CheckConstraint("best_site_ba >= 0", name="regulations_best_site_ba_check"),
        CheckConstraint("binding_affinity >= 0", name="regulations_binding_affinity_check"),
    )


class Sequence(Base):
    """序列存储表"""

    __tablename__ = "sequences"

    sequence_id = Column(BigInteger, primary_key=True, autoincrement=True)
    regulation_id = Column(
        BigInteger, ForeignKey("regulations.regulation_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    lncrna_sequence = Column(Text)
    dna_sequence = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    # 关系
    regulation = relationship("Regulation", back_populates="sequence")


class Trait(Base):
    """疾病/性状表"""

    __tablename__ = "traits"

    trait_id = Column(Integer, primary_key=True, autoincrement=True)
    trait_doid = Column(String(50), unique=True)
    trait_name = Column(String(200), nullable=False)
    trait_category = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    # 关系
    gene_associations = relationship("TraitGeneAssociation", back_populates="trait")


class Ontology(Base):
    """本体/功能分类表"""

    __tablename__ = "ontologies"

    ontology_id = Column(Integer, primary_key=True, autoincrement=True)
    ontology_cl_id = Column(String(50), unique=True)
    ontology_name = Column(String(200), nullable=False)
    ontology_type = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    # 关系
    gene_associations = relationship("TraitGeneAssociation", back_populates="ontology")


class TraitGeneAssociation(Base):
    """性状-基因关联表"""

    __tablename__ = "trait_gene_associations"

    association_id = Column(Integer, primary_key=True, autoincrement=True)
    core_id = Column(Integer, ForeignKey("core_genes.core_id"), nullable=False)
    trait_id = Column(Integer, ForeignKey("traits.trait_id"), nullable=False)
    ontology_id = Column(Integer, ForeignKey("ontologies.ontology_id"), nullable=False)
    odds_ratio = Column(Numeric(10, 4))
    fdr = Column(Numeric(10, 6))
    trait_snp_pvalue = Column(Numeric(15, 10))
    ontology_mw_pvalue = Column(Numeric(10, 6))
    ontology_fold_enrichment = Column(Numeric(10, 4))
    literature_support = Column(Boolean)
    evidence_species_id = Column(Integer, ForeignKey("species.species_id"), default=1)
    source_table = Column(String(100))
    source_row_number = Column(Integer)
    created_at = Column(DateTime, default=utc_now)

    # 关系
    core_gene = relationship("CoreGene", back_populates="trait_associations")
    trait = relationship("Trait", back_populates="gene_associations")
    ontology = relationship("Ontology", back_populates="gene_associations")

    __table_args__ = (
        UniqueConstraint(
            "core_id", "trait_id", "ontology_id", name="trait_gene_associations_core_id_trait_id_ontology_id_key"
        ),
    )


class FeatureTrack(Base):
    """Feature Track Registry (RepeatMasker, Conservation, etc.)"""

    __tablename__ = "feature_tracks"

    track_id = Column(Integer, primary_key=True, autoincrement=True)
    track_name = Column(String(100), unique=True, nullable=False, index=True)
    track_category = Column(String(50), nullable=False)  # 'repeat', 'epigenetic', 'conservation'
    display_name = Column(String(200), nullable=False)
    display_color = Column(String(20))
    attribute_schema = Column(JSONB)  # JSON Schema for attribute validation
    source_database = Column(String(100))
    version = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    features = relationship("GenomicFeature", back_populates="track")


class GenomicFeature(Base):
    """Genomic Features (RepeatMasker annotations, etc.) - Partitioned by species_id"""

    __tablename__ = "genomic_features"

    feature_id = Column(BigInteger, primary_key=True, autoincrement=True)
    track_id = Column(Integer, ForeignKey("feature_tracks.track_id"), nullable=False)
    species_id = Column(Integer, ForeignKey("species.species_id"), primary_key=True, nullable=False)
    chromosome = Column(String(20), nullable=False)
    feature_start = Column(BigInteger, nullable=False)
    feature_end = Column(BigInteger, nullable=False)
    feature_name = Column(String(200))
    strand = Column(String(1))  # '+', '-', '.'
    score = Column(Numeric(12, 6))
    attributes = Column(JSONB)  # Flexible storage: {'repeat_class': 'LINE', 'repeat_family': 'L1', 'divergence': 12.3}
    batch_id = Column(Integer, ForeignKey("import_batches.batch_id"))
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    track = relationship("FeatureTrack", back_populates="features")
    species = relationship("Species")
    batch = relationship("ImportBatch")

    __table_args__ = (
        Index("idx_gf_location", "chromosome", "feature_start", "feature_end"),
        CheckConstraint("feature_start >= 0", name="genomic_features_feature_start_check"),
        CheckConstraint("feature_end > feature_start", name="genomic_features_check"),
        CheckConstraint("strand IN ('+', '-', '.')", name="genomic_features_strand_check"),
        {"postgresql_partition_by": "LIST (species_id)"},
    )


# =============================================================================
# ChIP-seq Epigenetic Marks Models
# =============================================================================

class EpigeneticMarkType(Base):
    """Reference table for histone modification types"""

    __tablename__ = "epigenetic_mark_types"

    mark_type_id = Column(Integer, primary_key=True, autoincrement=True)
    mark_name = Column(String(50), unique=True, nullable=False, index=True)
    mark_category = Column(String(30), nullable=False)  # 'repressive', 'activating', 'bivalent_component'
    display_name = Column(String(100), nullable=False)
    display_color = Column(String(20), default='#666666')
    description = Column(Text)
    typical_signal_range = Column(JSONB)
    biological_function = Column(Text)
    associated_state = Column(String(100))
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=100)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    experiments = relationship("ChIPSeqExperiment", back_populates="mark_type")

    __table_args__ = (
        CheckConstraint(
            "mark_category IN ('repressive', 'activating', 'bivalent_component', 'open_chromatin', 'structural', 'other')",
            name="chk_mark_category"
        ),
    )


class MarkRelationship(Base):
    """Relationships between different epigenetic marks"""

    __tablename__ = "mark_relationships"

    relationship_id = Column(Integer, primary_key=True, autoincrement=True)
    mark_type_id_1 = Column(Integer, ForeignKey("epigenetic_mark_types.mark_type_id"), nullable=False)
    mark_type_id_2 = Column(Integer, ForeignKey("epigenetic_mark_types.mark_type_id"), nullable=False)
    relationship_type = Column(String(50), nullable=False)  # 'bivalent_pair', 'antagonistic', 'synergistic'
    description = Column(Text)
    biological_significance = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    mark_1 = relationship("EpigeneticMarkType", foreign_keys=[mark_type_id_1])
    mark_2 = relationship("EpigeneticMarkType", foreign_keys=[mark_type_id_2])

    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('bivalent_pair', 'antagonistic', 'synergistic', 'co_occurring', 'mutually_exclusive')",
            name="chk_relationship_type"
        ),
        UniqueConstraint("mark_type_id_1", "mark_type_id_2", name="unique_mark_pair"),
        CheckConstraint("mark_type_id_1 < mark_type_id_2", name="chk_different_marks"),
    )


class ChIPSeqExperiment(Base):
    """ChIP-seq experiment metadata"""

    __tablename__ = "chipseq_experiments"

    experiment_id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_name = Column(String(200), nullable=False)
    species_id = Column(Integer, ForeignKey("species.species_id"), nullable=False)
    mark_type_id = Column(Integer, ForeignKey("epigenetic_mark_types.mark_type_id"), nullable=False)

    # Sample/Cell information
    cell_type = Column(String(200))
    tissue_type = Column(String(200))
    cell_line = Column(String(200))
    treatment = Column(String(200))

    # Data source information
    source_database = Column(String(100))
    source_accession = Column(String(100))
    data_url = Column(Text)

    # Processing information
    pipeline_version = Column(String(50))
    peak_caller = Column(String(50))
    peak_caller_version = Column(String(50))
    reference_genome = Column(String(50))

    # Quality metrics
    total_reads = Column(BigInteger)
    mapped_reads = Column(BigInteger)
    duplicate_rate = Column(Numeric(5, 4))
    frip_score = Column(Numeric(5, 4))

    # Signal thresholds
    signal_threshold = Column(JSONB)
    mark_specific_config = Column(JSONB)

    # Metadata
    import_batch_id = Column(Integer, ForeignKey("import_batches.batch_id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    species = relationship("Species")
    mark_type = relationship("EpigeneticMarkType", back_populates="experiments")
    batch = relationship("ImportBatch")
    peaks = relationship("ChIPSeqPeak", back_populates="experiment")

    __table_args__ = (
        UniqueConstraint("experiment_name", "species_id", name="unique_experiment_name_species"),
        Index("idx_chipseq_exp_species", "species_id"),
        Index("idx_chipseq_exp_mark_type", "mark_type_id"),
        Index("idx_chipseq_exp_species_mark", "species_id", "mark_type_id"),
    )


class ChIPSeqPeak(Base):
    """ChIP-seq peak calls - Partitioned by species_id"""

    __tablename__ = "chipseq_peaks"

    peak_id = Column(BigInteger, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("chipseq_experiments.experiment_id"), nullable=False)
    species_id = Column(Integer, ForeignKey("species.species_id"), primary_key=True, nullable=False)

    # Genomic location
    chromosome = Column(String(20), nullable=False)
    peak_start = Column(BigInteger, nullable=False)
    peak_end = Column(BigInteger, nullable=False)
    summit_position = Column(BigInteger)

    # Peak identification
    peak_name = Column(String(200))
    strand = Column(String(1), default='.')

    # Signal strength metrics
    fold_enrichment = Column(Numeric(10, 4))
    log2_fold_enrichment = Column(Numeric(8, 4))
    pvalue = Column(Numeric(15, 10))
    neg_log10_pvalue = Column(Numeric(10, 4))
    qvalue = Column(Numeric(15, 10))
    neg_log10_qvalue = Column(Numeric(10, 4))
    signal_value = Column(Numeric(10, 4))

    # Peak quality
    score = Column(Integer)

    # Additional attributes
    attributes = Column(JSONB, default=dict)

    # Metadata
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    experiment = relationship("ChIPSeqExperiment", back_populates="peaks")
    species = relationship("Species")

    __table_args__ = (
        Index("idx_chipseq_peaks_location", "species_id", "chromosome", "peak_start", "peak_end"),
        Index("idx_chipseq_peaks_exp_location", "experiment_id", "chromosome", "peak_start", "peak_end"),
        Index("idx_chipseq_peaks_signal", "experiment_id", "fold_enrichment"),
        CheckConstraint("peak_start >= 0", name="chk_peak_start"),
        CheckConstraint("peak_end > peak_start", name="chk_peak_coordinates"),
        CheckConstraint("strand IN ('+', '-', '.')", name="chk_peak_strand"),
        {"postgresql_partition_by": "LIST (species_id)"},
    )

    @property
    def peak_width(self) -> int:
        """Calculate peak width"""
        return self.peak_end - self.peak_start


class GenePeakAssociation(Base):
    """Pre-computed gene-peak relationships for faster queries"""

    __tablename__ = "gene_peak_associations"

    association_id = Column(BigInteger, primary_key=True, autoincrement=True)
    gene_id = Column(Integer, ForeignKey("genes.gene_id"), nullable=False)
    peak_id = Column(BigInteger, nullable=False)
    species_id = Column(Integer, ForeignKey("species.species_id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("chipseq_experiments.experiment_id"), nullable=False)

    # Relationship type
    overlap_type = Column(String(30), nullable=False)  # 'promoter', 'gene_body', 'upstream', etc.
    distance_to_tss = Column(Integer)
    overlap_bp = Column(Integer)
    overlap_percentage = Column(Numeric(5, 2))

    # Cached peak info
    peak_fold_enrichment = Column(Numeric(10, 4))
    peak_qvalue = Column(Numeric(15, 10))

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    gene = relationship("Gene")
    species = relationship("Species")
    experiment = relationship("ChIPSeqExperiment")

    __table_args__ = (
        Index("idx_gene_peak_assoc_gene", "gene_id"),
        Index("idx_gene_peak_assoc_exp", "experiment_id"),
        Index("idx_gene_peak_assoc_gene_exp", "gene_id", "experiment_id"),
        UniqueConstraint("gene_id", "peak_id", "species_id", name="unique_gene_peak"),
        CheckConstraint(
            "overlap_type IN ('promoter', 'gene_body', 'tss', 'tes', 'upstream', 'downstream', 'intergenic', 'overlapping')",
            name="chk_overlap_type"
        ),
    )
