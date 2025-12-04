-- ============================================================================
-- Human LncRNA Atlas - Extension Phase 2 Schema
-- RepeatMasker and Genomic Features Support
-- Version: 2.3.1
-- Date: 2025-12-04
-- ============================================================================

-- ============================================================================
-- Table 1: feature_tracks (Track Configuration/Registry)
-- Purpose: Store metadata for different genomic feature tracks
-- ============================================================================

CREATE TABLE IF NOT EXISTS feature_tracks (
    track_id SERIAL PRIMARY KEY,
    track_name VARCHAR(100) UNIQUE NOT NULL,
    track_category VARCHAR(50) NOT NULL,  -- 'repeat', 'epigenetic', 'conservation'
    display_name VARCHAR(200) NOT NULL,
    display_color VARCHAR(20),
    attribute_schema JSONB,  -- JSON schema for attributes validation
    source_database VARCHAR(100),
    version VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for track lookup
CREATE INDEX IF NOT EXISTS idx_feature_tracks_name ON feature_tracks(track_name);
CREATE INDEX IF NOT EXISTS idx_feature_tracks_category ON feature_tracks(track_category);

COMMENT ON TABLE feature_tracks IS 'Registry of genomic feature track types (RepeatMasker, conservation, etc.)';
COMMENT ON COLUMN feature_tracks.track_name IS 'Unique identifier for the track (e.g., repeatmasker_repeats)';
COMMENT ON COLUMN feature_tracks.track_category IS 'Track category: repeat, epigenetic, conservation';
COMMENT ON COLUMN feature_tracks.attribute_schema IS 'JSON Schema for validating track-specific attributes';

-- Initialize RepeatMasker track
INSERT INTO feature_tracks (track_name, track_category, display_name, display_color, source_database, attribute_schema)
VALUES (
    'repeatmasker_repeats',
    'repeat',
    'RepeatMasker Annotations',
    '#E67E22',
    'RepeatMasker',
    '{
        "type": "object",
        "properties": {
            "repeat_class": {"type": "string", "description": "Repeat class (LINE, SINE, LTR, DNA, etc.)"},
            "repeat_family": {"type": "string", "description": "Repeat family (L1, Alu, etc.)"},
            "divergence": {"type": "number", "minimum": 0, "maximum": 100, "description": "Percent divergence from consensus"}
        },
        "required": ["repeat_class", "repeat_family"]
    }'::jsonb
)
ON CONFLICT (track_name) DO NOTHING;


-- ============================================================================
-- Table 2: genomic_features (Partitioned by species_id)
-- Purpose: Store genomic feature annotations with flexible attributes
-- ============================================================================

CREATE TABLE IF NOT EXISTS genomic_features (
    feature_id BIGSERIAL,
    track_id INTEGER NOT NULL REFERENCES feature_tracks(track_id),
    species_id INTEGER NOT NULL REFERENCES species(species_id),
    chromosome VARCHAR(20) NOT NULL,
    feature_start BIGINT NOT NULL,
    feature_end BIGINT NOT NULL,
    feature_name VARCHAR(200),
    strand VARCHAR(1) CHECK (strand IN ('+', '-', '.')),
    score DECIMAL(12, 6),
    attributes JSONB,  -- Flexible storage for track-specific fields
    batch_id INTEGER REFERENCES import_batches(batch_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (species_id, feature_id),
    CHECK (feature_start >= 0 AND feature_end > feature_start)
) PARTITION BY LIST (species_id);

COMMENT ON TABLE genomic_features IS 'Partitioned table for genomic feature annotations (RepeatMasker, etc.)';
COMMENT ON COLUMN genomic_features.attributes IS 'JSONB for track-specific attributes (e.g., repeat_class, repeat_family, divergence for RepeatMasker)';

-- ============================================================================
-- Create partitions for 4 species
-- ============================================================================

-- Human (species_id = 1)
CREATE TABLE IF NOT EXISTS genomic_features_human
    PARTITION OF genomic_features FOR VALUES IN (1);

-- Chimpanzee (species_id = 2)
CREATE TABLE IF NOT EXISTS genomic_features_chimp
    PARTITION OF genomic_features FOR VALUES IN (2);

-- Macaque (species_id = 3)
CREATE TABLE IF NOT EXISTS genomic_features_macaque
    PARTITION OF genomic_features FOR VALUES IN (3);

-- Marmoset (species_id = 4)
CREATE TABLE IF NOT EXISTS genomic_features_marmoset
    PARTITION OF genomic_features FOR VALUES IN (4);


-- ============================================================================
-- Create indexes for each partition
-- ============================================================================

-- Human partition indexes
CREATE INDEX IF NOT EXISTS idx_gf_human_track
    ON genomic_features_human(track_id);
CREATE INDEX IF NOT EXISTS idx_gf_human_location
    ON genomic_features_human(chromosome, feature_start, feature_end);
CREATE INDEX IF NOT EXISTS idx_gf_human_chr_track
    ON genomic_features_human(chromosome, track_id);
CREATE INDEX IF NOT EXISTS idx_gf_human_attrs
    ON genomic_features_human USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_gf_human_batch
    ON genomic_features_human(batch_id);

-- Chimpanzee partition indexes
CREATE INDEX IF NOT EXISTS idx_gf_chimp_track
    ON genomic_features_chimp(track_id);
CREATE INDEX IF NOT EXISTS idx_gf_chimp_location
    ON genomic_features_chimp(chromosome, feature_start, feature_end);
CREATE INDEX IF NOT EXISTS idx_gf_chimp_chr_track
    ON genomic_features_chimp(chromosome, track_id);
CREATE INDEX IF NOT EXISTS idx_gf_chimp_attrs
    ON genomic_features_chimp USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_gf_chimp_batch
    ON genomic_features_chimp(batch_id);

-- Macaque partition indexes
CREATE INDEX IF NOT EXISTS idx_gf_macaque_track
    ON genomic_features_macaque(track_id);
CREATE INDEX IF NOT EXISTS idx_gf_macaque_location
    ON genomic_features_macaque(chromosome, feature_start, feature_end);
CREATE INDEX IF NOT EXISTS idx_gf_macaque_chr_track
    ON genomic_features_macaque(chromosome, track_id);
CREATE INDEX IF NOT EXISTS idx_gf_macaque_attrs
    ON genomic_features_macaque USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_gf_macaque_batch
    ON genomic_features_macaque(batch_id);

-- Marmoset partition indexes
CREATE INDEX IF NOT EXISTS idx_gf_marmoset_track
    ON genomic_features_marmoset(track_id);
CREATE INDEX IF NOT EXISTS idx_gf_marmoset_location
    ON genomic_features_marmoset(chromosome, feature_start, feature_end);
CREATE INDEX IF NOT EXISTS idx_gf_marmoset_chr_track
    ON genomic_features_marmoset(chromosome, track_id);
CREATE INDEX IF NOT EXISTS idx_gf_marmoset_attrs
    ON genomic_features_marmoset USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_gf_marmoset_batch
    ON genomic_features_marmoset(batch_id);


-- ============================================================================
-- Utility views for common queries
-- ============================================================================

-- View: RepeatMasker features with flattened attributes
CREATE OR REPLACE VIEW v_repeatmasker_features AS
SELECT
    gf.feature_id,
    gf.species_id,
    s.species_code,
    s.display_name AS species_name,
    gf.chromosome,
    gf.feature_start,
    gf.feature_end,
    gf.feature_name AS repeat_name,
    gf.strand,
    gf.score,
    gf.attributes->>'repeat_class' AS repeat_class,
    gf.attributes->>'repeat_family' AS repeat_family,
    CAST(gf.attributes->>'divergence' AS DECIMAL(10,2)) AS divergence,
    gf.batch_id,
    gf.created_at
FROM genomic_features gf
JOIN feature_tracks ft ON gf.track_id = ft.track_id
JOIN species s ON gf.species_id = s.species_id
WHERE ft.track_name = 'repeatmasker_repeats';

COMMENT ON VIEW v_repeatmasker_features IS 'Flattened view of RepeatMasker annotations for easy querying';


-- ============================================================================
-- Statistics tracking
-- ============================================================================

-- Create function to get feature counts by track and species
CREATE OR REPLACE FUNCTION get_feature_track_stats()
RETURNS TABLE (
    track_name VARCHAR(100),
    display_name VARCHAR(200),
    species_id INTEGER,
    species_name VARCHAR(100),
    feature_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ft.track_name,
        ft.display_name,
        gf.species_id,
        s.display_name,
        COUNT(gf.feature_id)
    FROM feature_tracks ft
    LEFT JOIN genomic_features gf ON ft.track_id = gf.track_id
    LEFT JOIN species s ON gf.species_id = s.species_id
    WHERE ft.is_active = TRUE
    GROUP BY ft.track_name, ft.display_name, gf.species_id, s.display_name
    ORDER BY ft.track_name, gf.species_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_feature_track_stats() IS 'Get feature counts by track and species';


-- ============================================================================
-- Verification queries (run after execution)
-- ============================================================================

-- Verify table creation
SELECT
    tablename,
    tableowner
FROM pg_tables
WHERE tablename IN ('feature_tracks', 'genomic_features',
                    'genomic_features_human', 'genomic_features_chimp',
                    'genomic_features_macaque', 'genomic_features_marmoset');

-- Verify track initialization
SELECT * FROM feature_tracks;

-- Verify partition structure
SELECT
    parent.relname AS parent_table,
    child.relname AS partition_name
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'genomic_features';

-- Show index information
SELECT
    indexname,
    tablename
FROM pg_indexes
WHERE tablename LIKE 'genomic_features%'
ORDER BY tablename, indexname;
