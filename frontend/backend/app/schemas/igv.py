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


class IGVTrack(BaseModel):
    """IGV Track 配置"""
    name: str
    type: str
    format: str
    url: str
    indexURL: Optional[str] = None
    displayMode: Optional[str] = "EXPANDED"
    color: Optional[str] = None
    height: Optional[int] = None
    visibilityWindow: Optional[int] = None
    # 标签显示相关配置
    labelFields: Optional[str] = None
    defaultLabelFields: Optional[str] = None
    nameField: Optional[str] = None
    expandedRowHeight: Optional[int] = None
    squishedRowHeight: Optional[int] = None


class IGVConfig(BaseModel):
    """IGV.js 完整配置"""
    genome: Optional[str] = None
    reference: Optional[GenomeReference] = None
    locus: str
    tracks: List[IGVTrack]


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
