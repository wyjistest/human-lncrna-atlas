"""
SQLAlchemy ORM 模型
映射数据库表结构
"""
from datetime import datetime, timezone


def utc_now():
    """返回当前 UTC 时间（兼容 Python 3.12+，避免弃用的 utcnow()）"""
    return datetime.now(timezone.utc)
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
)
from sqlalchemy.orm import relationship

from app.core.database import Base


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
    core_id = Column(Integer, ForeignKey("core_genes.core_id"), nullable=False)
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
    lncrna_start = Column(BigInteger)  # 与 dna_start/end 保持一致，避免大坐标溢出
    lncrna_end = Column(BigInteger)    # 与 dna_start/end 保持一致，避免大坐标溢出
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
