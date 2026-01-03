"""
IGV.js 集成相关的 Pydantic 模型
"""
from typing import Optional, List
from pydantic import BaseModel


class GenomeReference(BaseModel):
    """基因组参考配置

    支持两种模式:
    1. 内置基因组 (如 hg19): 只需设置 id，其他字段为 None
    2. 自定义基因组: 使用 twoBitURL (推荐) 或 fastaURL + indexURL

    twoBitURL 格式优势:
    - 支持 HTTP Range 请求，只下载需要的序列片段
    - 比 .fa.gz 格式加载更快，特别适合远程访问
    - IGV.js 原生支持 UCSC 2bit 格式
    """
    id: str
    name: str
    fastaURL: Optional[str] = None
    indexURL: Optional[str] = None
    cytobandURL: Optional[str] = None
    twoBitURL: Optional[str] = None  # UCSC 2bit format for better performance
    chromSizesURL: Optional[str] = None  # Optional: chromosome sizes file URL
    aliasURL: Optional[str] = None  # Optional: chromosome alias table (e.g., hg19_alias.tab)


class IGVTrack(BaseModel):
    """IGV Track 配置"""
    name: str
    type: str
    format: str
    url: str
    # 可选：IGV.js webservice 轨道
    # 当 sourceType="service" 且 url 包含 $CHR/$START/$END 占位符时，IGV 会按当前视窗区域动态请求数据。
    sourceType: Optional[str] = None
    indexURL: Optional[str] = None
    displayMode: Optional[str] = "EXPANDED"
    color: Optional[str] = None
    height: Optional[int] = None
    # Wig/BigWig 可视化相关参数（可选）
    min: Optional[float] = None
    max: Optional[float] = None
    graphType: Optional[str] = None
    windowFunction: Optional[str] = None
    autoscaleGroup: Optional[str] = None
    colorScale: Optional[dict] = None
    visibilityWindow: Optional[int] = None
    # 标签显示相关配置
    labelFields: Optional[str] = None
    defaultLabelFields: Optional[str] = None
    nameField: Optional[str] = None
    expandedRowHeight: Optional[int] = None
    squishedRowHeight: Optional[int] = None


class IGVSearchConfig(BaseModel):
    """IGV.js 搜索配置

    用于配置 IGV.js 的搜索功能，指定搜索 API URL 和字段映射。
    """
    url: str  # 搜索 API URL，包含 $FEATURE$ 占位符
    chromosomeField: str = "chromosome"  # 染色体字段名
    startField: str = "start"  # 起始位置字段名
    endField: str = "end"  # 结束位置字段名


class IGVConfig(BaseModel):
    """IGV.js 完整配置"""
    genome: Optional[str] = None
    reference: Optional[GenomeReference] = None
    locus: str
    tracks: List[IGVTrack]
    search: Optional[IGVSearchConfig] = None  # 搜索配置


class IGVConfigResponse(BaseModel):
    """IGV 配置响应"""
    success: bool
    data: IGVConfig
    message: str


class SpeciesGenomeInfo(BaseModel):
    """物种基因组信息"""
    species_id: int
    species_name: str
    genome_assembly: str
    reference: GenomeReference
    available: bool


class IGVSearchResult(BaseModel):
    """IGV.js 搜索结果

    符合 IGV.js 期望的搜索结果格式，用于基因/位置搜索。
    IGV.js 会使用 chromosomeField, startField, endField 配置来解析这些字段。
    """
    chromosome: str  # 染色体，如 "chr10"
    start: int  # 起始位置 (0-based)
    end: int  # 结束位置
    gene: Optional[str] = None  # 基因名（可选，用于显示）


class GeneAutocompleteItem(BaseModel):
    """基因自动补全列表项

    用于前端搜索框下拉列表显示，包含 IGV 定位所需的基本信息。
    """
    gene_name: str  # 基因名称
    chromosome: str  # 染色体
    start: int  # 起始位置
    end: int  # 结束位置
    species_id: int  # 物种 ID


class GeneAutocompleteResponse(BaseModel):
    """基因自动补全响应"""
    success: bool
    data: List[GeneAutocompleteItem]
