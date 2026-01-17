-- ============================================================================
-- Extended Histone Modifications Update Script
-- Updates 3 marks with new display colors and descriptions as per requirements
-- Date: 2024-12-09
-- ============================================================================

-- H4K20me3: Update to match new specification (repressive/heterochromatin)
-- Current: #B22222, 'Constitutive heterochromatin; DNA damage response'
-- New: #6C3483, 'Heterochromatin, constitutive silencing'
UPDATE epigenetic_mark_types
SET
    display_color = '#6C3483',
    biological_function = 'Heterochromatin, constitutive silencing',
    sort_order = 17
WHERE mark_name = 'H4K20me3';

-- H3K56ac: Update to match new specification (activating/DNA repair)
-- Current: #4169E1, 'Nucleosome assembly; DNA replication', category='other'
-- New: #48C9B0, 'DNA replication and repair', category='activating'
UPDATE epigenetic_mark_types
SET
    mark_category = 'activating',
    display_color = '#48C9B0',
    biological_function = 'DNA replication and repair',
    sort_order = 18
WHERE mark_name = 'H3K56ac';

-- CTCF: Update to match new specification (structural/insulator)
-- Current: #FF8C00, 'Chromatin insulator; 3D genome organization'
-- New: #E74C3C, 'Insulator binding, chromatin organization'
UPDATE epigenetic_mark_types
SET
    display_color = '#E74C3C',
    biological_function = 'Insulator binding, chromatin organization',
    sort_order = 19
WHERE mark_name = 'CTCF';

-- Verify the updates
SELECT
    mark_type_id,
    mark_name,
    mark_category,
    display_name,
    display_color,
    biological_function,
    sort_order
FROM epigenetic_mark_types
WHERE mark_name IN ('H4K20me3', 'H3K56ac', 'CTCF')
ORDER BY sort_order;
