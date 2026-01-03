"""
IGV基因组配置
包含基因组参考、轨道配置和ChIP-seq颜色配置
"""
from typing import Optional

# =============================================================================
# ChIP-seq Mark Colors Configuration
# =============================================================================
# Default colors for common histone modifications
# These are used when mark colors are not defined in the database (epigenetic_mark_types.display_color)
CHIPSEQ_MARK_COLORS = {
    "H3K27me3": "#9B59B6",  # Purple - Repressive mark (Polycomb complex)
    "H3K4me1": "#F39C12",   # Orange - Enhancer mark
    "H3K4me3": "#27AE60",   # Green - Active promoter
    "H3K27ac": "#3498DB",   # Blue - Active enhancer
    "H3K36me3": "#1ABC9C",  # Teal - Transcription elongation
    "H3K9me3": "#E74C3C",   # Red - Heterochromatin/repressive
    "H3K9ac": "#3498DB",    # Blue - Active transcription
    "H3K4me2": "#27AE60",   # Green - Active chromatin
    "H3K79me2": "#1ABC9C",  # Teal - Transcription elongation
    "H2AZ": "#8E44AD",      # Dark purple - Variant histone
    "H3K56ac": "#2980B9",   # Dark blue - Transcription/repair
    "DNase-HS": "#FF6B35",  # Orange-red - Open chromatin (DNase-seq)
}

# Default color for unknown mark types
DEFAULT_CHIPSEQ_COLOR = "#7F8C8D"  # Gray


def get_track_name_prefix(mark_name: str, mark_category: Optional[str] = None) -> str:
    """
    Get the appropriate track name prefix based on mark type/category.

    - DNase-HS → "Open Chromatin"
    - ATAC-seq (future) → "Open Chromatin"
    - Others → "ChIP-seq"
    """
    # Open chromatin assays
    if mark_name in ("DNase-HS", "ATAC-seq"):
        return "Open Chromatin"
    if mark_category == "other" and "DNase" in mark_name:
        return "Open Chromatin"
    # Default to ChIP-seq for histone modifications
    return "ChIP-seq"

# =============================================================================
# Genome Reference Configuration
# =============================================================================
# 基因组参考配置
# 版本与项目数据一致: hg19, panTro5, rheMac10, calJac3
#
# 配置策略:
# - Human (hg19): 使用 IGV.js 内置基因组 ID，自动从 IGV 服务器加载
# - 其他灵长类: 使用 UCSC 2bit 格式，支持 HTTP Range 请求实现快速随机访问
#
# 2bit 格式优势 (相比 .fa.gz):
# - 支持 byte-range 请求，只下载需要的序列片段
# - 不需要全文件下载，加载速度快
# - IGV.js 原生支持 UCSC 2bit 格式
#
# 注意：IGV.js 内置支持的基因组列表见 https://igv.org/genomes/genomes.json
GENOME_REFERENCES = {
    1: {  # Human (hg19/GRCh37) - IGV.js 内置支持
        "id": "hg19",
        "name": "Human (GRCh37/hg19)",
        "fastaURL": None,  # Use built-in genome
        "indexURL": None,
        "cytobandURL": None,
        "twoBitURL": None,  # Not needed for built-in genome
        # 说明：hg19 的离线化（twoBit/cytoband/alias/chromSizes）由 get_genome_reference() 在运行时按文件存在性决定
    },
    2: {  # Chimp (panTro5) - Use 2bit format for better performance
        "id": "panTro5",
        "name": "Chimpanzee (Pan_tro_2.1.4/panTro5)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": "/genomes/cytoBand.panTro5.txt.gz",  # Local path
        "twoBitURL": "/genomes/panTro5.2bit",  # Local path
        "chromSizesURL": "/genomes/panTro5.chrom.sizes",
    },
    3: {  # Macaque (rheMac10) - Use 2bit format for better performance
        "id": "rheMac10",
        "name": "Rhesus Macaque (Mmul_10/rheMac10)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": "/genomes/cytoBand.rheMac10.txt.gz",  # Local path
        "twoBitURL": "/genomes/rheMac10.2bit",  # Local path
        "chromSizesURL": "/genomes/rheMac10.chrom.sizes",
    },
    4: {  # Marmoset (calJac3) - Use 2bit format for better performance
        "id": "calJac3",
        "name": "Marmoset (Callithrix_jacchus-3.2/calJac3)",
        "fastaURL": None,  # Don't use FASTA, use 2bit instead
        "indexURL": None,
        "cytobandURL": None,  # calJac3 does not have cytoBand data in UCSC
        "twoBitURL": "/genomes/calJac3.2bit",  # Local path
        "chromSizesURL": "/genomes/calJac3.chrom.sizes",
    },
}

# 物种名称映射
SPECIES_NAMES = {
    1: "Human",
    2: "Chimpanzee",
    3: "Rhesus Macaque",
    4: "Marmoset",
}

# 基因注释轨道配置
# 每个物种的基因注释 BigBed 文件路径
GENE_ANNOTATION_TRACKS = {
    2: {  # Chimpanzee (panTro5)
        "name": "Ensembl Genes (Pan_tro_3.0)",
        "url": "/genomes/panTro5_genes.bb",
        "description": "Gene annotations from Ensembl release 97",
    },
    3: {  # Macaque (rheMac10)
        "name": "Ensembl Genes (Mmul_10)",
        "url": "/genomes/rheMac10_genes.bb",
        "description": "Gene annotations from Ensembl release 98",
    },
    4: {  # Marmoset (calJac3)
        "name": "Ensembl Genes (C_jacchus3.2.1)",
        "url": "/genomes/calJac3_genes.bb",
        "description": "Gene annotations from Ensembl release 78",
    },
}

# ChIP-seq BigBed 轨道配置 (Human only, species_id=1)
# Each BigBed file contains all marks for a specific cell type
# BED9 format with itemRgb for color-coded marks
CHIPSEQ_BIGBED_TRACKS = {
    "K562": {
        "name": "ChIP-seq: K562 (Leukemia)",
        "url": "/genomes/chipseq_K562.bb",
        "color": "#E53935",  # Red
        "description": "All ChIP-seq marks for K562 leukemia cell line",
    },
    "GM12878": {
        "name": "ChIP-seq: GM12878 (B-lymphocyte)",
        "url": "/genomes/chipseq_GM12878.bb",
        "color": "#1E88E5",  # Blue
        "description": "All ChIP-seq marks for GM12878 B-lymphocyte",
    },
    "H1-hESC": {
        "name": "ChIP-seq: H1-hESC (Stem Cell)",
        "url": "/genomes/chipseq_H1_hESC.bb",
        "color": "#43A047",  # Green
        "description": "All ChIP-seq marks for H1-hESC embryonic stem cell",
    },
    "HepG2": {
        "name": "ChIP-seq: HepG2 (Liver Cancer)",
        "url": "/genomes/chipseq_HepG2.bb",
        "color": "#FB8C00",  # Orange
        "description": "All ChIP-seq marks for HepG2 hepatocellular carcinoma",
    },
    "A549": {
        "name": "ChIP-seq: A549 (Lung Cancer)",
        "url": "/genomes/chipseq_A549.bb",
        "color": "#8E24AA",  # Purple
        "description": "All ChIP-seq marks for A549 lung adenocarcinoma",
    },
    "MCF-7": {
        "name": "ChIP-seq: MCF-7 (Breast Cancer)",
        "url": "/genomes/chipseq_MCF7.bb",
        "color": "#FF69B4",  # Hot Pink
        "description": "All ChIP-seq marks for MCF-7 breast adenocarcinoma",
    },
    "HMEC": {
        "name": "ChIP-seq: HMEC (Normal Breast)",
        "url": "/genomes/chipseq_HMEC.bb",
        "color": "#DEB887",  # Burlywood
        "description": "All ChIP-seq marks for HMEC normal mammary epithelial",
    },
}
