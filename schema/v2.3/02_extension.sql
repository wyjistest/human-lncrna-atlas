-- ============================================================================
-- 多物种lncRNA调控网络数据库 - 扩展层Schema
-- ============================================================================
-- 版本: v2.3
-- 日期: 2025-11-20
-- 阶段: Phase 2（可选，非MVP必需）
-- 依赖: 01_core.sql
-- 用途: RepeatMasker、ChIP-seq、Conservation等基因组特征数据
-- ============================================================================

-- ============================================================================
-- 重要提示
-- ============================================================================
-- 本文件包含的表属于Phase 2扩展层，**不是MVP必需的**。
-- MVP阶段只需执行 01_core.sql。
-- 当需要添加RepeatMasker、H3K27me3等数据时再执行本文件。
-- ============================================================================

\echo '========================================='
\echo 'Phase 2 扩展层Schema开始执行'
\echo '注意: 本阶段为可选扩展功能'
\echo '========================================='

-- ============================================================================
-- 1. feature_tracks - 数据轨道注册表
-- ============================================================================

CREATE TABLE feature_tracks (
    track_id SERIAL PRIMARY KEY,
    track_name VARCHAR(100) UNIQUE NOT NULL,    -- 'repeatmasker_repeats'
    track_category VARCHAR(50),                   -- 'repeat', 'epigenetic', 'conservation'
    display_name VARCHAR(200),                    -- 'RepeatMasker Annotations'
    description TEXT,

    -- 字段schema定义（JSONB格式）
    attribute_schema JSONB,                       -- 定义此类型的字段schema

    -- 前端展示配置
    display_color VARCHAR(20),                    -- 前端显示颜色（如#FF5733）
    display_order INTEGER DEFAULT 100,           -- 前端排序权重

    -- 数据源信息
    source_database VARCHAR(100),                 -- UCSC, ENCODE, etc.
    source_version VARCHAR(50),                   -- 数据版本
    source_url TEXT,                              -- 数据来源URL

    -- 状态管理
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE feature_tracks IS 'Phase 2扩展层：数据轨道类型注册表';
COMMENT ON COLUMN feature_tracks.attribute_schema IS 'JSONB定义此类型的字段schema，如{"fold_enrichment": "float", "qvalue": "float"}';

CREATE INDEX idx_tracks_category ON feature_tracks(track_category);
CREATE INDEX idx_tracks_active ON feature_tracks(is_active) WHERE is_active = TRUE;

-- 预定义常用tracks
INSERT INTO feature_tracks (track_name, track_category, display_name, display_color) VALUES
('repeatmasker_repeats', 'repeat', 'RepeatMasker Annotations', '#8B4513'),
('h3k27me3_peaks', 'epigenetic', 'H3K27me3 ChIP-seq Peaks', '#9B59B6'),
('h3k4me3_peaks', 'epigenetic', 'H3K4me3 ChIP-seq Peaks', '#E74C3C'),
('h3k9me3_peaks', 'epigenetic', 'H3K9me3 ChIP-seq Peaks', '#3498DB'),
('multiz_conserved', 'conservation', 'Multiz Conservation Scores', '#27AE60');

-- ============================================================================
-- 2. genomic_features - 通用基因组特征表（分区）
-- ============================================================================

CREATE TABLE genomic_features (
    feature_id BIGSERIAL,
    track_id INTEGER NOT NULL REFERENCES feature_tracks(track_id),
    species_id INTEGER NOT NULL REFERENCES species(species_id) ON DELETE CASCADE,

    -- 基因组位置
    chromosome VARCHAR(20) NOT NULL,
    feature_start BIGINT NOT NULL CHECK (feature_start >= 0),
    feature_end BIGINT NOT NULL CHECK (feature_end > feature_start),
    strand CHAR(1) CHECK (strand IN ('+', '-', '.')),

    -- Phase 2优化：INT8RANGE列
    region INT8RANGE GENERATED ALWAYS AS (int8range(feature_start, feature_end)) STORED,

    -- 通用字段
    feature_name VARCHAR(200),                    -- repeat名称、peak ID等
    score DECIMAL(12, 6),                         -- 通用分数字段

    -- 类型特异属性（JSONB存储）
    attributes JSONB,                              -- 灵活存储各种类型的特异字段

    -- 来源追踪
    batch_id INTEGER REFERENCES import_batches(batch_id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (species_id, feature_id)
) PARTITION BY LIST (species_id);

COMMENT ON TABLE genomic_features IS 'Phase 2扩展层：通用基因组特征（分区表）';
COMMENT ON COLUMN genomic_features.region IS 'INT8RANGE列，支持GiST索引的高效范围查询';
COMMENT ON COLUMN genomic_features.attributes IS 'JSONB存储类型特异字段，如RepeatMasker的repeat_family或ChIP-seq的qvalue';

-- 为每个物种创建分区
CREATE TABLE genomic_features_human PARTITION OF genomic_features FOR VALUES IN (1);
CREATE TABLE genomic_features_chimp PARTITION OF genomic_features FOR VALUES IN (2);
CREATE TABLE genomic_features_macaque PARTITION OF genomic_features FOR VALUES IN (3);
CREATE TABLE genomic_features_marmoset PARTITION OF genomic_features FOR VALUES IN (4);

COMMENT ON TABLE genomic_features_human IS 'Human (Homo sapiens) 分区';
COMMENT ON TABLE genomic_features_chimp IS 'Chimpanzee (Pan troglodytes) 分区';
COMMENT ON TABLE genomic_features_macaque IS 'Macaque (Macaca mulatta) 分区';
COMMENT ON TABLE genomic_features_marmoset IS 'Marmoset (Callithrix jacchus) 分区';

-- 每个分区的索引（以human为例，其他分区类似）
CREATE INDEX idx_gf_human_track ON genomic_features_human(track_id);
CREATE INDEX idx_gf_human_chr ON genomic_features_human(chromosome);
CREATE INDEX idx_gf_human_track_chr ON genomic_features_human(track_id, chromosome);
CREATE INDEX idx_gf_human_region ON genomic_features_human USING GIST (region);
CREATE INDEX idx_gf_human_score ON genomic_features_human(score) WHERE score IS NOT NULL;
CREATE INDEX idx_gf_human_attributes ON genomic_features_human USING GIN (attributes);
CREATE INDEX idx_gf_human_batch ON genomic_features_human(batch_id);

-- chimp分区索引
CREATE INDEX idx_gf_chimp_track ON genomic_features_chimp(track_id);
CREATE INDEX idx_gf_chimp_chr ON genomic_features_chimp(chromosome);
CREATE INDEX idx_gf_chimp_track_chr ON genomic_features_chimp(track_id, chromosome);
CREATE INDEX idx_gf_chimp_region ON genomic_features_chimp USING GIST (region);
CREATE INDEX idx_gf_chimp_attributes ON genomic_features_chimp USING GIN (attributes);

-- macaque分区索引
CREATE INDEX idx_gf_macaque_track ON genomic_features_macaque(track_id);
CREATE INDEX idx_gf_macaque_chr ON genomic_features_macaque(chromosome);
CREATE INDEX idx_gf_macaque_track_chr ON genomic_features_macaque(track_id, chromosome);
CREATE INDEX idx_gf_macaque_region ON genomic_features_macaque USING GIST (region);
CREATE INDEX idx_gf_macaque_attributes ON genomic_features_macaque USING GIN (attributes);

-- marmoset分区索引
CREATE INDEX idx_gf_marmoset_track ON genomic_features_marmoset(track_id);
CREATE INDEX idx_gf_marmoset_chr ON genomic_features_marmoset(chromosome);
CREATE INDEX idx_gf_marmoset_track_chr ON genomic_features_marmoset(track_id, chromosome);
CREATE INDEX idx_gf_marmoset_region ON genomic_features_marmoset USING GIST (region);
CREATE INDEX idx_gf_marmoset_attributes ON genomic_features_marmoset USING GIN (attributes);

-- ============================================================================
-- 3. feature_gene_links - Feature与基因的关联表
-- ============================================================================

CREATE TABLE feature_gene_links (
    link_id BIGSERIAL PRIMARY KEY,
    feature_id BIGINT NOT NULL,
    species_id INTEGER NOT NULL,
    gene_id INTEGER NOT NULL REFERENCES genes(gene_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES feature_tracks(track_id),

    -- 关联类型
    link_type VARCHAR(50),                        -- 'overlap', 'promoter', 'enhancer', 'intron'

    -- 关联度量
    overlap_length BIGINT,                        -- 重叠长度
    distance_to_tss INTEGER,                      -- 距离TSS的距离（可为负）
    signal_strength DECIMAL(10, 4),               -- 信号强度（如ChIP-seq的fold_enrichment）

    -- 计算批次
    batch_id INTEGER REFERENCES import_batches(batch_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束（引用分区表需要包含species_id）
    FOREIGN KEY (species_id, feature_id) REFERENCES genomic_features(species_id, feature_id) ON DELETE CASCADE
);

COMMENT ON TABLE feature_gene_links IS 'Phase 2扩展层：Feature与基因的关联关系';
COMMENT ON COLUMN feature_gene_links.link_type IS '关联类型：overlap=完全重叠, promoter=启动子区域, enhancer=增强子';

CREATE INDEX idx_fgl_feature ON feature_gene_links(species_id, feature_id);
CREATE INDEX idx_fgl_gene ON feature_gene_links(gene_id);
CREATE INDEX idx_fgl_track ON feature_gene_links(track_id);
CREATE INDEX idx_fgl_type ON feature_gene_links(link_type);
CREATE INDEX idx_fgl_batch ON feature_gene_links(batch_id);

-- ============================================================================
-- 4. experiments - 实验/样本信息表（可选）
-- ============================================================================

CREATE TABLE experiments (
    experiment_id SERIAL PRIMARY KEY,
    experiment_name VARCHAR(200) UNIQUE NOT NULL,
    experiment_type VARCHAR(50),                  -- 'ChIP-seq', 'RNA-seq', 'ATAC-seq'

    -- 样本信息
    species_id INTEGER REFERENCES species(species_id),
    tissue VARCHAR(100),
    cell_type VARCHAR(100),
    cell_line VARCHAR(100),
    developmental_stage VARCHAR(50),

    -- 实验条件
    treatment VARCHAR(100),
    antibody VARCHAR(100),                        -- ChIP-seq用

    -- 数据来源
    source_database VARCHAR(50),                  -- 'ENCODE', 'GEO', 'ArrayExpress'
    source_accession VARCHAR(100),                -- GSE123456, ENCSR000AAA
    publication_pmid VARCHAR(20),

    -- 元数据
    metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE experiments IS 'Phase 2扩展层：实验/样本信息表（可选）';

CREATE INDEX idx_exp_species ON experiments(species_id);
CREATE INDEX idx_exp_type ON experiments(experiment_type);
CREATE INDEX idx_exp_tissue ON experiments(tissue);

-- ============================================================================
-- 5. experiment_features - 实验-Feature关联表（可选）
-- ============================================================================

CREATE TABLE experiment_features (
    experiment_id INTEGER REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    feature_id BIGINT NOT NULL,
    species_id INTEGER NOT NULL,

    -- 实验特异度量
    signal_value DECIMAL(12, 6),                  -- ChIP-seq信号值
    pvalue DECIMAL(15, 10),
    qvalue DECIMAL(15, 10),
    fold_enrichment DECIMAL(10, 4),

    PRIMARY KEY (experiment_id, species_id, feature_id),
    FOREIGN KEY (species_id, feature_id) REFERENCES genomic_features(species_id, feature_id) ON DELETE CASCADE
);

COMMENT ON TABLE experiment_features IS 'Phase 2扩展层：实验-Feature关联（可选）';

CREATE INDEX idx_expf_exp ON experiment_features(experiment_id);
CREATE INDEX idx_expf_feature ON experiment_features(species_id, feature_id);

-- ============================================================================
-- 扩展层完成
-- ============================================================================

\echo '========================================='
\echo 'Phase 2 扩展层Schema执行完成'
\echo ''
\echo '已创建表:'
\echo '  - feature_tracks (5行预定义数据)'
\echo '  - genomic_features (4个物种分区)'
\echo '  - feature_gene_links'
\echo '  - experiments (可选)'
\echo '  - experiment_features (可选)'
\echo ''
\echo '总计: 5张表 + 4个分区'
\echo '========================================='

-- 验证扩展层表数量
SELECT 'Extension Layer Tables' AS check_type, COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('feature_tracks', 'genomic_features', 'feature_gene_links', 'experiments', 'experiment_features');
