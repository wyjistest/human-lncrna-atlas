-- ============================================================================
-- 样本测试数据
-- ============================================================================
-- 版本: v2.3 (修正版 - 与01_core.sql完全兼容)
-- 用途: 提供最小测试数据集，用于快速验证数据库功能
-- 行数: 每表10-50行
-- 执行: psql -d lncrna_network -f schema/v2.3/03_sample_data.sql
-- ============================================================================

\echo '========================================='
\echo '插入样本测试数据'
\echo '========================================='

-- 已有数据: species (4行) - 由01_core.sql创建
-- 无需额外插入

-- ============================================================================
-- core_id_assignments + core_genes (10个核心基因)
-- ============================================================================

-- 手动分配10个core_id（注意：只有4列）
INSERT INTO core_id_assignments (core_id, assignment_source, notes)
VALUES
(10001, 'manual_test', 'Sample BRCA1 core gene'),
(10002, 'manual_test', 'Sample TP53 core gene'),
(10003, 'manual_test', 'Sample lncRNA 1'),
(10004, 'manual_test', 'Sample lncRNA 2'),
(10005, 'ortholog_table', 'Chimp BRCA1 ortholog'),
(10006, 'ortholog_table', 'Chimp TP53 ortholog'),
(10007, 'ortholog_table', 'Macaque BRCA1 ortholog'),
(10008, 'ortholog_table', 'Macaque TP53 ortholog'),
(10009, 'ortholog_table', 'Marmoset BRCA1 ortholog'),
(10010, 'ortholog_table', 'Marmoset TP53 ortholog');

INSERT INTO core_genes (core_id, gene_type, canonical_symbol, human_ensembl_id)
VALUES
(10001, 'protein_coding', 'BRCA1', 'ENSG00000012048'),
(10002, 'protein_coding', 'TP53', 'ENSG00000141510'),
(10003, 'lncRNA', 'RP11-13K12.1', NULL),
(10004, 'lncRNA', 'RP11-45K23.2', NULL),
-- 跨物种同源基因（chimp）
(10005, 'protein_coding', 'BRCA1', 'ENSG00000012048'),  -- chimp BRCA1 (maps to human)
(10006, 'protein_coding', 'TP53', 'ENSG00000141510'),   -- chimp TP53
-- 跨物种同源基因（macaque）
(10007, 'protein_coding', 'BRCA1', 'ENSG00000012048'),  -- macaque BRCA1
(10008, 'protein_coding', 'TP53', 'ENSG00000141510'),   -- macaque TP53
-- 跨物种同源基因（marmoset）
(10009, 'protein_coding', 'BRCA1', 'ENSG00000012048'),  -- marmoset BRCA1
(10010, 'protein_coding', 'TP53', 'ENSG00000141510');   -- marmoset TP53

-- ============================================================================
-- genes (12条基因记录，注意：没有gene_type列！)
-- ============================================================================

INSERT INTO genes (species_id, core_id, gene_ensembl_id, gene_name, chromosome, gene_start, gene_end, strand)
VALUES
-- Human (species_id=1)
(1, 10001, 'ENSG00000012048', 'BRCA1', 'chr17', 43044295, 43125483, '-'),
(1, 10002, 'ENSG00000141510', 'TP53', 'chr17', 7661779, 7687550, '-'),
(1, 10003, 'CATG00000000034', 'RP11-13K12.1', 'chr1', 1000000, 1005000, '+'),
(1, 10004, 'CATG00000000045', 'RP11-45K23.2', 'chr10', 81137057, 81210122, '+'),
(1, NULL, 'ENSG00000165424', 'GATA3', 'chr10', 8050500, 8125000, '+'),

-- Chimp (species_id=2)
(2, 10005, 'ENSPTRG00000001234', 'BRCA1', 'chr17', 43000000, 43100000, '-'),
(2, 10006, 'ENSPTRG00000005678', 'TP53', 'chr17', 7650000, 7680000, '-'),
(2, NULL, 'ENSPTRG00000011111', 'GATA3', 'chr10', 8040000, 8120000, '+'),

-- Macaque (species_id=3)
(3, 10007, 'ENSMMUG00000012345', 'BRCA1', 'chr17', 42900000, 43000000, '-'),
(3, 10008, 'ENSMMUG00000067890', 'TP53', 'chr17', 7640000, 7670000, '-'),

-- Marmoset (species_id=4)
(4, 10009, 'ENSCJAG00000011111', 'BRCA1', 'chr17', 42800000, 42900000, '-'),
(4, 10010, 'ENSCJAG00000022222', 'TP53', 'chr17', 7630000, 7660000, '-');

-- ============================================================================
-- traits + ontologies (各5条，注意：trait_doid不是trait_efo_id)
-- ============================================================================

INSERT INTO traits (trait_name, trait_category, trait_doid)
VALUES
('autism spectrum disorder', 'neurological', 'DOID:0060041'),
('breast cancer', 'cancer', 'DOID:1612'),
('schizophrenia', 'neurological', 'DOID:5419'),
('diabetes mellitus', 'metabolic', 'DOID:9351'),
('alzheimer disease', 'neurological', 'DOID:10652');

INSERT INTO ontologies (ontology_cl_id, ontology_name, ontology_type)
VALUES
('CL:0000540', 'middle temporal gyrus', 'brain'),
('CL:0000128', 'oligodendrocyte', 'brain'),
('CL:0000057', 'fibroblast', 'tissue'),
('CL:0000066', 'epithelial cell', 'tissue'),
('CL:0000236', 'B cell', 'immune');

-- ============================================================================
-- trait_gene_associations (10条关联)
-- ============================================================================

INSERT INTO trait_gene_associations
    (core_id, trait_id, ontology_id, odds_ratio, fdr, evidence_species_id)
VALUES
(10001, 2, 1, 1.45, 0.001, 1),  -- BRCA1 - breast cancer - MTG
(10001, 5, 1, 1.23, 0.005, 1),  -- BRCA1 - alzheimer - MTG
(10002, 1, 1, 1.67, 0.0001, 1), -- TP53 - autism - MTG
(10002, 2, 1, 2.01, 0.00001, 1),-- TP53 - breast cancer - MTG
(10001, 2, 3, 1.89, 0.002, 1),  -- BRCA1 - breast cancer - fibroblast
(10002, 3, 2, 1.34, 0.01, 1),   -- TP53 - schizophrenia - oligodendrocyte
(10001, 4, 4, 1.12, 0.05, 1),   -- BRCA1 - diabetes - epithelial
(10002, 1, 2, 1.56, 0.003, 1),  -- TP53 - autism - oligodendrocyte
(10001, 1, 1, 1.42, 0.008, 1),  -- BRCA1 - autism - MTG
(10002, 5, 1, 1.78, 0.0002, 1); -- TP53 - alzheimer - MTG

-- ============================================================================
-- import_batches (1个测试批次)
-- ============================================================================

INSERT INTO import_batches (batch_name, batch_type, species_id, status, record_count)
VALUES
('Sample Test Batch', 'regulations', 1, 'completed', 6);

-- ============================================================================
-- regulations (6条调控关系 - 注意：regulations表有很多列！)
-- ============================================================================

DO $$
DECLARE
    lncrna_1_id INT;
    lncrna_2_id INT;
    brca1_id INT;
    tp53_id INT;
    gata3_id INT;
    batch_id_var INT;  -- 改名避免与列名冲突
BEGIN
    -- 获取基因ID（带NULL检查）
    SELECT gene_id INTO lncrna_1_id FROM genes WHERE gene_ensembl_id = 'CATG00000000034';
    IF lncrna_1_id IS NULL THEN
        RAISE EXCEPTION 'Gene CATG00000000034 not found';
    END IF;

    SELECT gene_id INTO lncrna_2_id FROM genes WHERE gene_ensembl_id = 'CATG00000000045';
    IF lncrna_2_id IS NULL THEN
        RAISE EXCEPTION 'Gene CATG00000000045 not found';
    END IF;

    SELECT gene_id INTO brca1_id FROM genes WHERE gene_ensembl_id = 'ENSG00000012048';
    IF brca1_id IS NULL THEN
        RAISE EXCEPTION 'Gene ENSG00000012048 not found';
    END IF;

    SELECT gene_id INTO tp53_id FROM genes WHERE gene_ensembl_id = 'ENSG00000141510';
    IF tp53_id IS NULL THEN
        RAISE EXCEPTION 'Gene ENSG00000141510 not found';
    END IF;

    SELECT gene_id INTO gata3_id FROM genes WHERE gene_ensembl_id = 'ENSG00000165424';
    IF gata3_id IS NULL THEN
        RAISE EXCEPTION 'Gene ENSG00000165424 not found';
    END IF;

    SELECT batch_id INTO batch_id_var FROM import_batches WHERE batch_name = 'Sample Test Batch';
    IF batch_id_var IS NULL THEN
        RAISE EXCEPTION 'Batch "Sample Test Batch" not found';
    END IF;

    -- 插入调控关系（只包含regulations表实际存在的列）
    INSERT INTO regulations
        (species_id, lncrna_gene_id, target_gene_id, target_chromosome,
         target_start, target_end, binding_affinity, batch_id)
    VALUES
    (1, lncrna_1_id, brca1_id, 'chr17', 43044295, 43044350, 75.5, batch_id_var),
    (1, lncrna_1_id, tp53_id, 'chr17', 7661779, 7661830, 68.3, batch_id_var),
    (1, lncrna_1_id, gata3_id, 'chr10', 8050500, 8050555, 82.1, batch_id_var),
    (1, lncrna_2_id, brca1_id, 'chr17', 43050000, 43050060, 55.2, batch_id_var),
    (1, lncrna_2_id, tp53_id, 'chr17', 7665000, 7665055, 63.7, batch_id_var),
    (1, lncrna_2_id, gata3_id, 'chr10', 8055000, 8055050, 71.9, batch_id_var);

    RAISE NOTICE '成功插入 % 条regulations记录', 6;

EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'regulations插入失败: %', SQLERRM;
END $$;

-- ============================================================================
-- sequences (5条序列，演示可选性)
-- ============================================================================

DO $$
DECLARE
    reg_id INT;
BEGIN
    FOR reg_id IN (SELECT regulation_id FROM regulations LIMIT 5)
    LOOP
        INSERT INTO sequences (regulation_id, lncrna_sequence, dna_sequence)
        VALUES (
            reg_id,
            'ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT',  -- 示例lncRNA序列
            'TGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCA'   -- 示例DNA序列
        );
    END LOOP;
END $$;

-- ============================================================================
-- 验证样本数据
-- ============================================================================

\echo ''
\echo '样本数据统计:'
SELECT 'species' AS table_name, COUNT(*) AS row_count FROM species
UNION ALL SELECT 'core_genes', COUNT(*) FROM core_genes
UNION ALL SELECT 'genes', COUNT(*) FROM genes
UNION ALL SELECT 'traits', COUNT(*) FROM traits
UNION ALL SELECT 'ontologies', COUNT(*) FROM ontologies
UNION ALL SELECT 'trait_gene_associations', COUNT(*) FROM trait_gene_associations
UNION ALL SELECT 'regulations', COUNT(*) FROM regulations
UNION ALL SELECT 'sequences', COUNT(*) FROM sequences
UNION ALL SELECT 'import_batches', COUNT(*) FROM import_batches
ORDER BY table_name;

\echo ''
\echo '========================================='
\echo '样本数据插入完成'
\echo '实际行数: species=4, genes=12, regulations=6'
\echo '========================================='
