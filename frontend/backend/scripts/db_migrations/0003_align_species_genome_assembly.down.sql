-- Revert species.genome_assembly back to older defaults used in early schema seeds.
UPDATE species SET genome_assembly = 'hg38' WHERE species_code = 'human';
UPDATE species SET genome_assembly = 'panTro6' WHERE species_code = 'chimp';
UPDATE species SET genome_assembly = 'rheMac10' WHERE species_code = 'macaque';
UPDATE species SET genome_assembly = 'calJac4' WHERE species_code = 'marmoset';

