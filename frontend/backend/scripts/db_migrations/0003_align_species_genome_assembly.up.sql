-- Align species.genome_assembly with the assemblies actually used by IGV/data in this project.
-- This matches:
-- - schema/v2.3/01_core.sql
-- - frontend/backend/app/config/igv_genomes.py
UPDATE species SET genome_assembly = 'hg19' WHERE species_code = 'human';
UPDATE species SET genome_assembly = 'panTro5' WHERE species_code = 'chimp';
UPDATE species SET genome_assembly = 'rheMac10' WHERE species_code = 'macaque';
UPDATE species SET genome_assembly = 'calJac3' WHERE species_code = 'marmoset';

