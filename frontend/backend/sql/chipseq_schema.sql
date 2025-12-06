-- ============================================================================
-- ChIP-seq Epigenetic Marks Schema Extension
-- Unified architecture supporting multiple histone modifications
-- ============================================================================

-- ============================================================================
-- 1. MARK TYPES REFERENCE TABLE (Static Configuration)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epigenetic_mark_types (
    mark_type_id SERIAL PRIMARY KEY,
    mark_name VARCHAR(50) NOT NULL UNIQUE,                  -- 'H3K27me3', 'H3K4me1', etc.
    mark_category VARCHAR(30) NOT NULL,                     -- 'repressive', 'activating', 'bivalent_component'
    display_name VARCHAR(100) NOT NULL,                     -- 'Histone H3 lysine 27 trimethylation'
    display_color VARCHAR(20) DEFAULT '#666666',            -- Hex color for visualization
    description TEXT,
    typical_signal_range JSONB,                             -- {"min": 0, "max": 100, "unit": "fold_enrichment"}
    biological_function TEXT,                               -- Brief biological description
    associated_state VARCHAR(100),                          -- 'gene_silencing', 'active_enhancer', etc.
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_mark_category CHECK (
        mark_category IN ('repressive', 'activating', 'bivalent_component', 'structural', 'other')
    )
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_mark_types_name ON epigenetic_mark_types(mark_name);
CREATE INDEX IF NOT EXISTS idx_mark_types_category ON epigenetic_mark_types(mark_category);

-- ============================================================================
-- 2. MARK RELATIONSHIPS TABLE (For Bivalent Domains, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS mark_relationships (
    relationship_id SERIAL PRIMARY KEY,
    mark_type_id_1 INTEGER NOT NULL REFERENCES epigenetic_mark_types(mark_type_id),
    mark_type_id_2 INTEGER NOT NULL REFERENCES epigenetic_mark_types(mark_type_id),
    relationship_type VARCHAR(50) NOT NULL,                 -- 'bivalent_pair', 'antagonistic', 'synergistic'
    description TEXT,
    biological_significance TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_relationship_type CHECK (
        relationship_type IN ('bivalent_pair', 'antagonistic', 'synergistic', 'co_occurring', 'mutually_exclusive')
    ),
    CONSTRAINT unique_mark_pair UNIQUE (mark_type_id_1, mark_type_id_2),
    CONSTRAINT chk_different_marks CHECK (mark_type_id_1 < mark_type_id_2)
);

-- ============================================================================
-- 3. CHIPSEQ EXPERIMENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS chipseq_experiments (
    experiment_id SERIAL PRIMARY KEY,
    experiment_name VARCHAR(200) NOT NULL,
    species_id INTEGER NOT NULL REFERENCES species(species_id),
    mark_type_id INTEGER NOT NULL REFERENCES epigenetic_mark_types(mark_type_id),

    -- Sample/Cell information
    cell_type VARCHAR(200),                                 -- 'H1-hESC', 'K562', 'GM12878'
    tissue_type VARCHAR(200),                               -- 'brain', 'liver', 'blood'
    cell_line VARCHAR(200),                                 -- Specific cell line
    treatment VARCHAR(200),                                 -- Experimental treatment if any

    -- Data source information
    source_database VARCHAR(100),                           -- 'ENCODE', 'GEO', 'Custom'
    source_accession VARCHAR(100),                          -- 'ENCSR000AKP', 'GSE12345'
    data_url TEXT,                                          -- Direct link to raw data

    -- Processing information
    pipeline_version VARCHAR(50),                           -- 'ENCODE3', 'ChIP-seq_v2'
    peak_caller VARCHAR(50),                                -- 'MACS2', 'HOMER', 'SICER'
    peak_caller_version VARCHAR(50),
    reference_genome VARCHAR(50),                           -- 'GRCh38', 'hg38'

    -- Quality metrics
    total_reads BIGINT,
    mapped_reads BIGINT,
    duplicate_rate NUMERIC(5,4),
    frip_score NUMERIC(5,4),                                -- Fraction of Reads in Peaks

    -- Signal thresholds used
    signal_threshold JSONB,                                 -- {"qvalue_cutoff": 0.01, "fold_enrichment_min": 2.0}

    -- Mark-specific configuration (flexible)
    mark_specific_config JSONB,                             -- Mark-type specific processing parameters

    -- Metadata
    import_batch_id INTEGER REFERENCES import_batches(batch_id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one experiment per name+species
    CONSTRAINT unique_experiment_name_species UNIQUE (experiment_name, species_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_chipseq_exp_species ON chipseq_experiments(species_id);
CREATE INDEX IF NOT EXISTS idx_chipseq_exp_mark_type ON chipseq_experiments(mark_type_id);
CREATE INDEX IF NOT EXISTS idx_chipseq_exp_species_mark ON chipseq_experiments(species_id, mark_type_id);
CREATE INDEX IF NOT EXISTS idx_chipseq_exp_cell_type ON chipseq_experiments(cell_type);
CREATE INDEX IF NOT EXISTS idx_chipseq_exp_source ON chipseq_experiments(source_database, source_accession);
CREATE INDEX IF NOT EXISTS idx_chipseq_exp_active ON chipseq_experiments(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 4. CHIPSEQ PEAKS TABLE (Extends genomic_features concept, but dedicated)
-- ============================================================================
-- Option A: Use genomic_features with experiment_id in attributes
-- Option B: Dedicated chipseq_peaks table for better query performance
-- We choose Option B for optimal performance with ChIP-seq specific indexes

CREATE TABLE IF NOT EXISTS chipseq_peaks (
    peak_id BIGSERIAL,
    experiment_id INTEGER NOT NULL REFERENCES chipseq_experiments(experiment_id),
    species_id INTEGER NOT NULL REFERENCES species(species_id),

    -- Genomic location
    chromosome VARCHAR(20) NOT NULL,
    peak_start BIGINT NOT NULL,
    peak_end BIGINT NOT NULL,
    summit_position BIGINT,                                 -- Peak summit (highest signal point)

    -- Peak identification
    peak_name VARCHAR(200),                                 -- Original peak name from caller
    strand VARCHAR(1) DEFAULT '.',                          -- Usually '.' for ChIP-seq

    -- Signal strength metrics
    fold_enrichment NUMERIC(10,4),                          -- Fold enrichment over background
    log2_fold_enrichment NUMERIC(8,4),                      -- log2(fold_enrichment)
    pvalue NUMERIC(15,10),                                  -- Raw p-value
    neg_log10_pvalue NUMERIC(10,4),                         -- -log10(pvalue)
    qvalue NUMERIC(15,10),                                  -- FDR-corrected q-value
    neg_log10_qvalue NUMERIC(10,4),                         -- -log10(qvalue)
    signal_value NUMERIC(10,4),                             -- Signal value (RPM/RPKM normalized)

    -- Peak quality indicators
    score INTEGER,                                          -- BED score (0-1000)
    peak_width INTEGER GENERATED ALWAYS AS (peak_end - peak_start) STORED,

    -- Additional attributes (flexible)
    attributes JSONB DEFAULT '{}',

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Primary key includes species_id for partitioning
    PRIMARY KEY (peak_id, species_id),

    -- Constraints
    CONSTRAINT chk_peak_coordinates CHECK (peak_start >= 0 AND peak_end > peak_start),
    CONSTRAINT chk_summit_in_peak CHECK (
        summit_position IS NULL OR
        (summit_position >= peak_start AND summit_position <= peak_end)
    ),
    CONSTRAINT chk_strand CHECK (strand IN ('+', '-', '.'))
) PARTITION BY LIST (species_id);

-- Create partitions for known species
-- Human (species_id = 1)
CREATE TABLE IF NOT EXISTS chipseq_peaks_human PARTITION OF chipseq_peaks
    FOR VALUES IN (1);

-- Mouse (species_id = 2)
CREATE TABLE IF NOT EXISTS chipseq_peaks_mouse PARTITION OF chipseq_peaks
    FOR VALUES IN (2);

-- Default partition for other species
CREATE TABLE IF NOT EXISTS chipseq_peaks_default PARTITION OF chipseq_peaks
    DEFAULT;

-- ============================================================================
-- 5. INDEXES FOR CHIPSEQ_PEAKS (Critical for Performance)
-- ============================================================================

-- Genomic range queries (most important)
CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_location
    ON chipseq_peaks (species_id, chromosome, peak_start, peak_end);

-- GiST index for efficient overlap queries
CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_range
    ON chipseq_peaks USING GIST (
        species_id,
        chromosome,
        int8range(peak_start, peak_end, '[]')
    );

-- Experiment + location queries
CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_exp_location
    ON chipseq_peaks (experiment_id, chromosome, peak_start, peak_end);

-- Signal strength queries
CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_signal
    ON chipseq_peaks (experiment_id, fold_enrichment DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_qvalue
    ON chipseq_peaks (experiment_id, qvalue ASC NULLS LAST);

-- Peak width analysis
CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_width
    ON chipseq_peaks (experiment_id, peak_width);

-- JSONB attributes (for flexible filtering)
CREATE INDEX IF NOT EXISTS idx_chipseq_peaks_attrs
    ON chipseq_peaks USING GIN (attributes);

-- ============================================================================
-- 6. GENE-PEAK ASSOCIATIONS (Pre-computed for faster queries)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gene_peak_associations (
    association_id BIGSERIAL PRIMARY KEY,
    gene_id INTEGER NOT NULL REFERENCES genes(gene_id),
    peak_id BIGINT NOT NULL,
    species_id INTEGER NOT NULL REFERENCES species(species_id),
    experiment_id INTEGER NOT NULL REFERENCES chipseq_experiments(experiment_id),

    -- Relationship type
    overlap_type VARCHAR(30) NOT NULL,                      -- 'promoter', 'gene_body', 'upstream', 'downstream', 'intergenic'
    distance_to_tss INTEGER,                                -- Distance from TSS (negative = upstream)
    overlap_bp INTEGER,                                     -- Overlap length in bp
    overlap_percentage NUMERIC(5,2),                        -- Percentage of peak overlapping gene region

    -- Cached peak info for fast access
    peak_fold_enrichment NUMERIC(10,4),
    peak_qvalue NUMERIC(15,10),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_overlap_type CHECK (
        overlap_type IN ('promoter', 'gene_body', 'tss', 'tes', 'upstream', 'downstream', 'intergenic', 'overlapping')
    ),

    -- Prevent duplicate associations
    CONSTRAINT unique_gene_peak UNIQUE (gene_id, peak_id, species_id)
);

-- Indexes for gene-peak queries
CREATE INDEX IF NOT EXISTS idx_gene_peak_assoc_gene ON gene_peak_associations(gene_id);
CREATE INDEX IF NOT EXISTS idx_gene_peak_assoc_exp ON gene_peak_associations(experiment_id);
CREATE INDEX IF NOT EXISTS idx_gene_peak_assoc_gene_exp ON gene_peak_associations(gene_id, experiment_id);
CREATE INDEX IF NOT EXISTS idx_gene_peak_assoc_overlap ON gene_peak_associations(overlap_type);

-- ============================================================================
-- 7. MATERIALIZED VIEWS FOR STATISTICS (Optional, for Dashboard)
-- ============================================================================

-- Mark type statistics per species
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_chipseq_mark_stats AS
SELECT
    e.species_id,
    s.species_code,
    m.mark_name,
    m.mark_category,
    m.display_color,
    COUNT(DISTINCT e.experiment_id) as experiment_count,
    COUNT(p.peak_id) as total_peaks,
    AVG(p.fold_enrichment) as avg_fold_enrichment,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.fold_enrichment) as median_fold_enrichment,
    AVG(p.peak_width) as avg_peak_width
FROM chipseq_experiments e
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
JOIN species s ON e.species_id = s.species_id
LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
WHERE e.is_active = TRUE
GROUP BY e.species_id, s.species_code, m.mark_name, m.mark_category, m.display_color
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_chipseq_stats_unique
    ON mv_chipseq_mark_stats(species_id, mark_name);

-- Gene-level mark summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_gene_mark_summary AS
SELECT
    gpa.gene_id,
    e.species_id,
    m.mark_name,
    m.mark_category,
    COUNT(DISTINCT gpa.peak_id) as peak_count,
    MAX(gpa.peak_fold_enrichment) as max_fold_enrichment,
    AVG(gpa.peak_fold_enrichment) as avg_fold_enrichment,
    MIN(gpa.peak_qvalue) as best_qvalue,
    array_agg(DISTINCT gpa.overlap_type) as overlap_types
FROM gene_peak_associations gpa
JOIN chipseq_experiments e ON gpa.experiment_id = e.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE e.is_active = TRUE
GROUP BY gpa.gene_id, e.species_id, m.mark_name, m.mark_category
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_mv_gene_mark_gene ON mv_gene_mark_summary(gene_id);
CREATE INDEX IF NOT EXISTS idx_mv_gene_mark_species_mark ON mv_gene_mark_summary(species_id, mark_name);

-- ============================================================================
-- 8. REFRESH FUNCTION FOR MATERIALIZED VIEWS
-- ============================================================================
CREATE OR REPLACE FUNCTION refresh_chipseq_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_chipseq_mark_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_gene_mark_summary;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. INSERT INITIAL MARK TYPES DATA
-- ============================================================================
INSERT INTO epigenetic_mark_types (mark_name, mark_category, display_name, display_color, biological_function, associated_state, sort_order)
VALUES
    -- Repressive marks
    ('H3K27me3', 'repressive', 'Histone H3 lysine 27 trimethylation', '#DC143C',
     'Polycomb-mediated gene silencing; developmental gene repression', 'gene_silencing', 10),
    ('H3K9me3', 'repressive', 'Histone H3 lysine 9 trimethylation', '#8B0000',
     'Heterochromatin formation; transposon silencing', 'heterochromatin', 20),
    ('H4K20me3', 'repressive', 'Histone H4 lysine 20 trimethylation', '#B22222',
     'Constitutive heterochromatin; DNA damage response', 'heterochromatin', 30),
    ('H3K9me2', 'repressive', 'Histone H3 lysine 9 dimethylation', '#CD5C5C',
     'Gene silencing; nuclear periphery localization', 'gene_silencing', 35),

    -- Activating marks
    ('H3K4me1', 'activating', 'Histone H3 lysine 4 monomethylation', '#32CD32',
     'Enhancer marking; poised or active enhancers', 'enhancer', 40),
    ('H3K4me3', 'activating', 'Histone H3 lysine 4 trimethylation', '#228B22',
     'Active promoter marking; transcription initiation', 'active_promoter', 50),
    ('H3K27ac', 'activating', 'Histone H3 lysine 27 acetylation', '#00FF00',
     'Active enhancers and promoters; distinguishes active from poised enhancers', 'active_enhancer', 60),
    ('H3K36me3', 'activating', 'Histone H3 lysine 36 trimethylation', '#7CFC00',
     'Active transcription elongation; exon marking', 'transcription_elongation', 70),
    ('H3K4me2', 'activating', 'Histone H3 lysine 4 dimethylation', '#90EE90',
     'Active and poised enhancers/promoters', 'enhancer_promoter', 75),
    ('H3K79me2', 'activating', 'Histone H3 lysine 79 dimethylation', '#98FB98',
     'Transcription elongation; DNA damage response', 'transcription_elongation', 80),
    ('H3K9ac', 'activating', 'Histone H3 lysine 9 acetylation', '#00FA9A',
     'Active promoters; open chromatin', 'active_promoter', 85),

    -- Bivalent components (marks that can form bivalent domains)
    ('H3K4me3_H3K27me3', 'bivalent_component', 'Bivalent domain (H3K4me3 + H3K27me3)', '#FFD700',
     'Poised developmental genes; stem cell pluripotency', 'poised_bivalent', 90),

    -- Other/Structural
    ('H3K56ac', 'other', 'Histone H3 lysine 56 acetylation', '#4169E1',
     'Nucleosome assembly; DNA replication', 'chromatin_assembly', 100),
    ('H2A.Z', 'structural', 'Histone variant H2A.Z', '#9370DB',
     'Promoter architecture; gene regulation', 'promoter_structure', 110),
    ('CTCF', 'structural', 'CTCF binding sites', '#FF8C00',
     'Chromatin insulator; 3D genome organization', 'insulator', 120)
ON CONFLICT (mark_name) DO NOTHING;

-- ============================================================================
-- 10. INSERT MARK RELATIONSHIPS
-- ============================================================================
INSERT INTO mark_relationships (mark_type_id_1, mark_type_id_2, relationship_type, description, biological_significance)
SELECT
    m1.mark_type_id, m2.mark_type_id,
    'bivalent_pair',
    'H3K4me3 and H3K27me3 co-occurrence defines bivalent domains',
    'Bivalent domains poise developmental genes for rapid activation or silencing'
FROM epigenetic_mark_types m1, epigenetic_mark_types m2
WHERE m1.mark_name = 'H3K4me3' AND m2.mark_name = 'H3K27me3'
ON CONFLICT DO NOTHING;

INSERT INTO mark_relationships (mark_type_id_1, mark_type_id_2, relationship_type, description, biological_significance)
SELECT
    m1.mark_type_id, m2.mark_type_id,
    'antagonistic',
    'H3K27ac and H3K27me3 are mutually exclusive at the same residue',
    'These marks cannot co-exist on the same lysine residue'
FROM epigenetic_mark_types m1, epigenetic_mark_types m2
WHERE m1.mark_name = 'H3K27ac' AND m2.mark_name = 'H3K27me3'
ON CONFLICT DO NOTHING;

INSERT INTO mark_relationships (mark_type_id_1, mark_type_id_2, relationship_type, description, biological_significance)
SELECT
    m1.mark_type_id, m2.mark_type_id,
    'synergistic',
    'H3K4me1 and H3K27ac together mark active enhancers',
    'Co-occurrence indicates fully active enhancer elements'
FROM epigenetic_mark_types m1, epigenetic_mark_types m2
WHERE m1.mark_name = 'H3K4me1' AND m2.mark_name = 'H3K27ac'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 11. REGISTER CHIPSEQ TRACK IN FEATURE_TRACKS
-- ============================================================================
INSERT INTO feature_tracks (track_name, track_category, display_name, display_color, source_database, is_active, attribute_schema)
VALUES (
    'chipseq_epigenetic',
    'epigenetic',
    'ChIP-seq Histone Modifications',
    '#4169E1',
    'Multiple',
    TRUE,
    '{
        "type": "object",
        "properties": {
            "mark_type": {"type": "string"},
            "experiment_id": {"type": "integer"},
            "fold_enrichment": {"type": "number"},
            "qvalue": {"type": "number"},
            "pvalue": {"type": "number"}
        },
        "required": ["mark_type", "experiment_id"]
    }'::jsonb
)
ON CONFLICT (track_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    attribute_schema = EXCLUDED.attribute_schema;

-- ============================================================================
-- 12. HELPER FUNCTIONS
-- ============================================================================

-- Function to get mark_type_id by name
CREATE OR REPLACE FUNCTION get_mark_type_id(p_mark_name VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_mark_type_id INTEGER;
BEGIN
    SELECT mark_type_id INTO v_mark_type_id
    FROM epigenetic_mark_types
    WHERE mark_name = p_mark_name;

    IF v_mark_type_id IS NULL THEN
        RAISE EXCEPTION 'Mark type not found: %', p_mark_name;
    END IF;

    RETURN v_mark_type_id;
END;
$$ LANGUAGE plpgsql;

-- Function to check if peaks overlap with gene region
CREATE OR REPLACE FUNCTION get_gene_chipseq_peaks(
    p_gene_id INTEGER,
    p_mark_types TEXT[] DEFAULT NULL,
    p_flanking INTEGER DEFAULT 10000
)
RETURNS TABLE (
    peak_id BIGINT,
    experiment_id INTEGER,
    mark_name VARCHAR,
    mark_category VARCHAR,
    chromosome VARCHAR,
    peak_start BIGINT,
    peak_end BIGINT,
    fold_enrichment NUMERIC,
    qvalue NUMERIC,
    distance_to_tss INTEGER
) AS $$
DECLARE
    v_gene RECORD;
    v_region_start BIGINT;
    v_region_end BIGINT;
    v_tss BIGINT;
BEGIN
    -- Get gene information
    SELECT g.chromosome, g.gene_start, g.gene_end, g.strand, g.species_id
    INTO v_gene
    FROM genes g
    WHERE g.gene_id = p_gene_id;

    IF v_gene IS NULL THEN
        RAISE EXCEPTION 'Gene not found: %', p_gene_id;
    END IF;

    -- Calculate region and TSS
    v_region_start := GREATEST(0, v_gene.gene_start - p_flanking);
    v_region_end := v_gene.gene_end + p_flanking;
    v_tss := CASE WHEN v_gene.strand = '+' THEN v_gene.gene_start ELSE v_gene.gene_end END;

    RETURN QUERY
    SELECT
        p.peak_id,
        p.experiment_id,
        m.mark_name,
        m.mark_category,
        p.chromosome,
        p.peak_start,
        p.peak_end,
        p.fold_enrichment,
        p.qvalue,
        (CASE
            WHEN v_gene.strand = '+' THEN p.summit_position - v_tss
            ELSE v_tss - p.summit_position
        END)::INTEGER as distance_to_tss
    FROM chipseq_peaks p
    JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
    JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
    WHERE p.species_id = v_gene.species_id
      AND p.chromosome = v_gene.chromosome
      AND p.peak_start < v_region_end
      AND p.peak_end > v_region_start
      AND e.is_active = TRUE
      AND (p_mark_types IS NULL OR m.mark_name = ANY(p_mark_types));

END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 13. PERMISSIONS (adjust role names as needed)
-- ============================================================================
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
-- GRANT INSERT, UPDATE, DELETE ON chipseq_peaks, chipseq_experiments TO data_admin;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO data_admin;

COMMENT ON TABLE epigenetic_mark_types IS 'Reference table for histone modification types and their properties';
COMMENT ON TABLE chipseq_experiments IS 'ChIP-seq experiment metadata with mark type, cell type, and quality metrics';
COMMENT ON TABLE chipseq_peaks IS 'ChIP-seq peak calls partitioned by species for optimal query performance';
COMMENT ON TABLE gene_peak_associations IS 'Pre-computed gene-peak relationships for fast lookups';
COMMENT ON TABLE mark_relationships IS 'Biological relationships between different epigenetic marks';
COMMENT ON MATERIALIZED VIEW mv_chipseq_mark_stats IS 'Cached statistics per mark type and species';
COMMENT ON MATERIALIZED VIEW mv_gene_mark_summary IS 'Cached gene-level mark summaries';
