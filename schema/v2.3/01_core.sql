-- ============================================================================
-- 多物种lncRNA调控网络数据库 - MVP核心Schema
-- ============================================================================
-- 版本: v2.3 (文档同步修正版)
-- 日期: 2025-11-20
-- 修正历史:
--   v2.1: trait_gene_associations基于core_id + network_snapshots JSON契约 + 简化MVP
--   v2.2: gen_random_uuid()扩展 + core_id_seq连接 + JSON契约改用core_id作为key
--   v2.3: 与DATABASE_DESIGN_FINAL.md v2.3同步，确认不使用INT8RANGE/GiST索引
-- ============================================================================

-- ============================================================================
-- 0. 必需扩展
-- ============================================================================

-- 【修正】添加UUID生成扩展，否则gen_random_uuid()会失败
CREATE EXTENSION IF NOT EXISTS pgcrypto;

COMMENT ON EXTENSION pgcrypto IS '提供gen_random_uuid()函数用于network_jobs';

-- ============================================================================
-- 1. 物种表
-- ============================================================================

CREATE TABLE species (
    species_id SERIAL PRIMARY KEY,
    species_code VARCHAR(20) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    latin_name VARCHAR(100),
    genome_assembly VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE species IS '物种元数据';
COMMENT ON COLUMN species.species_code IS '物种代码: human, chimp, macaque, marmoset';
COMMENT ON COLUMN species.genome_assembly IS '基因组版本: hg38, panTro6等';

-- 预插入数据
-- 注意：genome_assembly 字段存储的是 UCSC Genome Browser 参考基因组版本
-- IGV 浏览器使用的版本：hg19 (人类), panTro5 (黑猩猩), rheMac10 (猕猴), calJac3 (狨猴)
INSERT INTO species (species_code, display_name, latin_name, genome_assembly) VALUES
('human', '人类', 'Homo sapiens', 'hg38'),
('chimp', '黑猩猩', 'Pan troglodytes', 'panTro6'),
('macaque', '猕猴', 'Macaca mulatta', 'rheMac10'),
('marmoset', '狨猴', 'Callithrix jacchus', 'calJac4');

-- ============================================================================
-- 2. core_id管理（修正：添加分配追踪）
-- ============================================================================

-- core_id自动生成序列（从100000000开始，避免与ortholog表冲突）
CREATE SEQUENCE core_id_seq START WITH 100000000 INCREMENT BY 1;

COMMENT ON SEQUENCE core_id_seq IS 'core_id自动生成序列，用于无同源关系的新基因';

-- 【修正】core_id添加DEFAULT，自动从序列生成
CREATE TABLE core_id_assignments (
    core_id INTEGER PRIMARY KEY DEFAULT nextval('core_id_seq'),
    assignment_source VARCHAR(50) NOT NULL,  -- 'ortholog_table', 'auto_generated'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

COMMENT ON TABLE core_id_assignments IS 'core_id分配来源追踪';
COMMENT ON COLUMN core_id_assignments.assignment_source IS 'ortholog_table: 来自同源表; auto_generated: 新基因自动生成';

-- ============================================================================
-- 3. 核心基因表（跨物种实体）
-- ============================================================================

CREATE TABLE core_genes (
    core_id INTEGER PRIMARY KEY REFERENCES core_id_assignments(core_id),
    gene_type VARCHAR(20) NOT NULL CHECK (gene_type IN ('lncRNA', 'protein_coding')),
    canonical_symbol VARCHAR(100),
    human_ensembl_id VARCHAR(50),       -- 人类参考ID
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE core_genes IS '跨物种基因实体，core_id是多物种映射的中心';
COMMENT ON COLUMN core_genes.canonical_symbol IS '标准基因符号（如BRCA1），优先用人类名称';

CREATE INDEX idx_core_genes_type ON core_genes(gene_type);

-- ============================================================================
-- 4. 物种特异基因表
-- ============================================================================

CREATE TABLE genes (
    gene_id SERIAL PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(species_id) ON DELETE CASCADE,
    core_id INTEGER REFERENCES core_genes(core_id),

    -- 基因标识
    gene_ensembl_id VARCHAR(50) NOT NULL,
    gene_name VARCHAR(100),

    -- 基因组位置
    chromosome VARCHAR(20),
    gene_start BIGINT CHECK (gene_start >= 0),
    gene_end BIGINT CHECK (gene_end > gene_start),
    strand CHAR(1) CHECK (strand IN ('+', '-', '.')),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(species_id, gene_ensembl_id)
);

COMMENT ON TABLE genes IS '物种特异基因，通过core_id映射到跨物种实体';
COMMENT ON COLUMN genes.gene_ensembl_id IS 'ENSG/CATG ID，带版本号';
COMMENT ON COLUMN genes.core_id IS '关联到core_genes，NULL表示该基因无同源信息';

-- 索引策略（重要！直接写明）
CREATE INDEX idx_genes_species ON genes(species_id);
CREATE INDEX idx_genes_core ON genes(core_id);
CREATE INDEX idx_genes_ensembl ON genes(gene_ensembl_id);
CREATE INDEX idx_genes_name ON genes(gene_name);
CREATE INDEX idx_genes_location ON genes(species_id, chromosome, gene_start, gene_end);

-- ============================================================================
-- 5. 性状/疾病表
-- ============================================================================

CREATE TABLE traits (
    trait_id SERIAL PRIMARY KEY,
    trait_doid VARCHAR(50) UNIQUE,
    trait_name VARCHAR(200) NOT NULL,
    trait_category VARCHAR(100),        -- 'cancer', 'neurological', 'metabolic'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE traits IS '性状/疾病，如autism spectrum disorder';

CREATE INDEX idx_traits_name ON traits(trait_name);
CREATE INDEX idx_traits_category ON traits(trait_category);

-- ============================================================================
-- 6. 组织/细胞类型表
-- ============================================================================

CREATE TABLE ontologies (
    ontology_id SERIAL PRIMARY KEY,
    ontology_cl_id VARCHAR(50) UNIQUE,
    ontology_name VARCHAR(200) NOT NULL,
    ontology_type VARCHAR(50),          -- 'brain', 'immune', 'tissue'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ontologies IS '组织/细胞类型，如middle temporal gyrus';

CREATE INDEX idx_ontologies_name ON ontologies(ontology_name);
CREATE INDEX idx_ontologies_type ON ontologies(ontology_type);

-- ============================================================================
-- 7. 性状-基因关联表 【修正：基于core_id】
-- ============================================================================

CREATE TABLE trait_gene_associations (
    association_id SERIAL PRIMARY KEY,

    -- 【修正】直接关联core_id而非gene_id
    core_id INTEGER NOT NULL REFERENCES core_genes(core_id),
    trait_id INTEGER NOT NULL REFERENCES traits(trait_id),
    ontology_id INTEGER NOT NULL REFERENCES ontologies(ontology_id),

    -- 统计信息（来自table15，基于人类数据）
    odds_ratio DECIMAL(10, 4),
    fdr DECIMAL(10, 6),
    trait_snp_pvalue DECIMAL(15, 10),
    ontology_mw_pvalue DECIMAL(10, 6),
    ontology_fold_enrichment DECIMAL(10, 4),
    literature_support BOOLEAN,

    -- 【新增】标记证据来源物种（重要！）
    evidence_species_id INTEGER REFERENCES species(species_id) DEFAULT 1,

    -- 来源追踪
    source_table VARCHAR(100),
    source_row_number INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(core_id, trait_id, ontology_id)
);

COMMENT ON TABLE trait_gene_associations IS '性状-基因关联，基于core_id支持多物种分析';
COMMENT ON COLUMN trait_gene_associations.core_id IS '【修正】挂在core_id上，支持跨物种查询';
COMMENT ON COLUMN trait_gene_associations.evidence_species_id IS '证据来源物种，默认1=human';

-- 索引策略
CREATE INDEX idx_tga_core ON trait_gene_associations(core_id);
CREATE INDEX idx_tga_trait ON trait_gene_associations(trait_id);
CREATE INDEX idx_tga_ontology ON trait_gene_associations(ontology_id);
CREATE INDEX idx_tga_composite ON trait_gene_associations(trait_id, ontology_id);

-- ============================================================================
-- 8. 导入批次追踪表
-- ============================================================================

CREATE TABLE import_batches (
    batch_id SERIAL PRIMARY KEY,
    batch_name VARCHAR(200) NOT NULL,
    batch_type VARCHAR(50),             -- 'regulations', 'repeatmasker', 'h3k27me3'
    species_id INTEGER REFERENCES species(species_id),

    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_file VARCHAR(500),
    record_count BIGINT,

    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'failed')),
    error_message TEXT,
    completed_at TIMESTAMP
);

COMMENT ON TABLE import_batches IS '数据导入批次追踪，支持失败回滚';

CREATE INDEX idx_batches_status ON import_batches(status);
CREATE INDEX idx_batches_type ON import_batches(batch_type);

-- ============================================================================
-- 9. 调控关系表（核心业务）
-- ============================================================================

CREATE TABLE regulations (
    regulation_id BIGSERIAL PRIMARY KEY,

    -- 批次追踪
    batch_id INTEGER REFERENCES import_batches(batch_id),

    -- 物种和基因
    species_id INTEGER NOT NULL REFERENCES species(species_id) ON DELETE CASCADE,
    lncrna_gene_id INTEGER NOT NULL REFERENCES genes(gene_id) ON DELETE CASCADE,
    target_gene_id INTEGER NOT NULL REFERENCES genes(gene_id) ON DELETE CASCADE,

    -- 目标区域
    target_chromosome VARCHAR(20),
    target_start BIGINT CHECK (target_start >= 0),
    target_end BIGINT CHECK (target_end > target_start),

    -- TFO统计
    tfo_file VARCHAR(255),
    total_sites INTEGER,
    kept_sites INTEGER,
    num_peaks INTEGER,

    -- 最佳Peak信息
    best_peak_num INTEGER,
    best_avg_ba DECIMAL(10, 4),
    best_num_sites INTEGER,
    best_peak_chr VARCHAR(20),
    best_peak_start BIGINT,
    best_peak_end BIGINT,
    best_site_ba DECIMAL(10, 4) CHECK (best_site_ba >= 0),

    -- 结合位点
    lncrna_start INTEGER,
    lncrna_end INTEGER,
    dna_start BIGINT,
    dna_end BIGINT,

    -- 快速筛选字段
    binding_affinity DECIMAL(10, 4) CHECK (binding_affinity >= 0),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE regulations IS 'lncRNA调控关系，核心业务表';
COMMENT ON COLUMN regulations.binding_affinity IS '结合亲和力，主要筛选字段';

-- 【修正】明确索引策略（来自审查意见）
CREATE INDEX idx_reg_species ON regulations(species_id);
CREATE INDEX idx_reg_lncrna ON regulations(lncrna_gene_id);
CREATE INDEX idx_reg_target ON regulations(target_gene_id);
CREATE INDEX idx_reg_batch ON regulations(batch_id);

-- 【重要】主力查询索引组合
CREATE INDEX idx_reg_species_lnc_ba ON regulations(species_id, lncrna_gene_id, binding_affinity DESC);
CREATE INDEX idx_reg_species_target ON regulations(species_id, target_gene_id);
CREATE INDEX idx_reg_ba ON regulations(binding_affinity) WHERE binding_affinity >= 50;

-- 位置查询索引
CREATE INDEX idx_reg_location ON regulations(target_chromosome, target_start, target_end);

-- 【重要】唯一约束用于ETL去重（ON CONFLICT DO NOTHING）
-- 该约束确保同一物种、同一lncRNA-target对、同一位置的调控关系只有一条记录
--
-- ⚠️ NULL 安全：使用 NULLS NOT DISTINCT (PostgreSQL 15+) 确保 NULL 值也参与去重
--   - lncrna_start/lncrna_end/dna_start/dna_end 允许为 NULL（表示位置未知）
--   - 默认情况下 NULL != NULL，会导致重复行
--   - NULLS NOT DISTINCT 将 NULL 视为相等值进行去重
--
-- ⚠️ 迁移注意：此索引仅用于新库初始化。
-- 对于存量数据库，请运行 etl/migrations/002_fix_regulations_unique_null_safe.sql 迁移脚本。
CREATE UNIQUE INDEX idx_regulations_unique_key
ON regulations (species_id, lncrna_gene_id, target_gene_id, lncrna_start, lncrna_end, dna_start, dna_end)
NULLS NOT DISTINCT;

-- ============================================================================
-- 10. 序列表（分离存储，按需加载）
-- ============================================================================

CREATE TABLE sequences (
    sequence_id BIGSERIAL PRIMARY KEY,
    regulation_id BIGINT NOT NULL REFERENCES regulations(regulation_id) ON DELETE CASCADE,

    lncrna_sequence TEXT,
    dna_sequence TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(regulation_id)
);

COMMENT ON TABLE sequences IS '调控序列，分离存储避免主表膨胀';

CREATE INDEX idx_seq_regulation ON sequences(regulation_id);

-- ============================================================================
-- 11. 网络生成任务表
-- ============================================================================

CREATE TABLE network_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 查询参数（输入）
    trait_id INTEGER REFERENCES traits(trait_id),
    ontology_id INTEGER REFERENCES ontologies(ontology_id),
    min_ba DECIMAL(10, 4) DEFAULT 50,
    species_ids INTEGER[],              -- 请求的物种列表

    -- 任务状态
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error_message TEXT,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

COMMENT ON TABLE network_jobs IS '网络生成任务，支持异步查询';

CREATE INDEX idx_jobs_status ON network_jobs(status);
CREATE INDEX idx_jobs_params ON network_jobs(trait_id, ontology_id, min_ba);

-- ============================================================================
-- 12. 网络快照表 【修正：明确JSON契约】
-- ============================================================================

CREATE TABLE network_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES network_jobs(job_id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL REFERENCES species(species_id),

    -- === 节点数据（JSON契约） ===
    -- 【二次修正】改为用core_id作为节点key，与trait_gene_associations设计一致，支持跨物种对比
    nodes JSONB NOT NULL,
    -- 契约结构：
    -- {
    --   "lncrnas": [12345, 67890, 11223],             // ✅ core_id列表（非species-specific ID）
    --   "targets": [99001, 99002, 99003],
    --   "dual_role": [88888],                         // 既是lncRNA又是target
    --   "names": {                                    // canonical基因名
    --     12345: "RP11-13K12.1",
    --     67890: "RP11-45K23.2",
    --     99001: "BRCA1",
    --     99002: "TP53"
    --   },
    --   "species_gene_ids": {                         // ✅ species-specific ID变为属性
    --     12345: "CATG00000000034.1",
    --     67890: "CATG00000000045.1",
    --     99001: "ENSG00000012048.1",
    --     99002: "ENSG00000141510.1"
    --   },
    --   "chromosomes": {                              // 可选：基因组位置
    --     12345: "chr1",
    --     99001: "chr17",
    --     99002: "chr17"
    --   }
    -- }
    -- 优势：
    --   1. 节点ID是core_id，跨物种对比时直接比较（humanNodes ∩ chimpNodes）
    --   2. 与trait_gene_associations的core_id设计一致
    --   3. 前端Cytoscape使用core_id作为node.id，物种切换时节点ID不变

    -- === 边数据（JSON契约） ===
    edges JSONB NOT NULL,
    -- 契约结构：
    -- [
    --   {
    --     "source": 12345,                            // ✅ lncRNA core_id（非species-specific ID）
    --     "target": 99001,                            // ✅ target core_id
    --     "weight": 75.5,                             // binding_affinity
    --     "regulation_id": 123456                     // regulations表主键（用于查序列等详情）
    --   },
    --   {
    --     "source": 67890,
    --     "target": 99002,
    --     "weight": 62.3,
    --     "regulation_id": 123457
    --   }
    -- ]

    -- === 统计数据（JSON契约） ===
    statistics JSONB NOT NULL,
    -- 契约结构：
    -- {
    --   "total_genes": 49,
    --   "lncrna_count": 18,
    --   "target_count": 31,
    --   "dual_role_count": 2,
    --   "regulation_count": 341,
    --   "ba_stats": {
    --     "min": 50.03,
    --     "max": 80.69,
    --     "median": 55.18,
    --     "mean": 56.2,
    --     "std": 5.3
    --   }
    -- }

    -- 可选：预渲染图像路径
    figure_path VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(job_id, species_id)
);

COMMENT ON TABLE network_snapshots IS '网络快照缓存，节点/边使用core_id作为key（支持跨物种对比）';
COMMENT ON COLUMN network_snapshots.nodes IS 'JSON契约：{lncrnas: [core_id...], targets, names, species_gene_ids, chromosomes}';
COMMENT ON COLUMN network_snapshots.edges IS 'JSON契约：[{source: core_id, target: core_id, weight, regulation_id}]';
COMMENT ON COLUMN network_snapshots.statistics IS 'JSON契约：{total_genes, lncrna_count, regulation_count, ba_stats}';

CREATE INDEX idx_snapshot_job ON network_snapshots(job_id);
CREATE INDEX idx_snapshot_species ON network_snapshots(species_id);

-- 【二次修正】JSON结构验证约束（检查core_id作为key的设计）
ALTER TABLE network_snapshots
    ADD CONSTRAINT check_nodes_structure
    CHECK (
        jsonb_typeof(nodes) = 'object' AND
        nodes ? 'lncrnas' AND
        nodes ? 'targets' AND
        nodes ? 'names' AND
        nodes ? 'species_gene_ids'  -- 改为species_gene_ids
    );

ALTER TABLE network_snapshots
    ADD CONSTRAINT check_edges_structure
    CHECK (jsonb_typeof(edges) = 'array');

ALTER TABLE network_snapshots
    ADD CONSTRAINT check_stats_structure
    CHECK (
        jsonb_typeof(statistics) = 'object' AND
        statistics ? 'total_genes' AND
        statistics ? 'regulation_count' AND
        statistics ? 'ba_stats'
    );

-- ============================================================================
-- 视图：简化常用查询
-- ============================================================================

-- 带基因名的调控关系视图
CREATE VIEW v_regulations_with_names AS
SELECT
    r.regulation_id,
    s.species_code,
    r.species_id,

    -- lncRNA信息
    lnc.gene_ensembl_id AS lncrna_id,
    lnc.gene_name AS lncrna_name,
    lnc.core_id AS lncrna_core_id,

    -- target信息
    tgt.gene_ensembl_id AS target_id,
    tgt.gene_name AS target_name,
    tgt.core_id AS target_core_id,

    -- 调控信息
    r.binding_affinity,
    r.best_peak_chr,
    r.best_peak_start,
    r.best_peak_end,
    r.regulation_id

FROM regulations r
JOIN species s ON r.species_id = s.species_id
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN genes tgt ON r.target_gene_id = tgt.gene_id;

COMMENT ON VIEW v_regulations_with_names IS '调控关系视图，包含基因名和core_id';

-- 性状-组织-基因统计视图（基于core_id）
CREATE VIEW v_trait_ontology_gene_stats AS
SELECT
    t.trait_id,
    t.trait_name,
    o.ontology_id,
    o.ontology_name,
    COUNT(DISTINCT tga.core_id) AS core_gene_count,
    COUNT(DISTINCT CASE WHEN cg.gene_type = 'lncRNA' THEN tga.core_id END) AS lncrna_count,
    COUNT(DISTINCT CASE WHEN cg.gene_type = 'protein_coding' THEN tga.core_id END) AS protein_count
FROM traits t
JOIN trait_gene_associations tga ON t.trait_id = tga.trait_id
JOIN ontologies o ON tga.ontology_id = o.ontology_id
JOIN core_genes cg ON tga.core_id = cg.core_id
GROUP BY t.trait_id, t.trait_name, o.ontology_id, o.ontology_name;

COMMENT ON VIEW v_trait_ontology_gene_stats IS '性状-组织关联统计，基于core_id计数';

-- ============================================================================
-- 完成信息
-- ============================================================================

-- 显示表统计
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

    RAISE NOTICE '========================================';
    RAISE NOTICE 'MVP Core Schema创建完成';
    RAISE NOTICE '========================================';
    RAISE NOTICE '总表数: %', table_count;
    RAISE NOTICE '核心业务表: 10张';
    RAISE NOTICE '缓存表: 2张';
    RAISE NOTICE '视图: 2个';
    RAISE NOTICE '';
    RAISE NOTICE '关键修正:';
    RAISE NOTICE '1. trait_gene_associations基于core_id';
    RAISE NOTICE '2. network_snapshots明确JSON契约';
    RAISE NOTICE '3. regulations表明确索引策略';
    RAISE NOTICE '';
    RAISE NOTICE '下一步:';
    RAISE NOTICE '1. 执行数据导入脚本';
    RAISE NOTICE '2. 验证核心查询性能';
    RAISE NOTICE '========================================';
END $$;
