"""
IGV.js 集成相关的 Pydantic 模型
"""
from typing import Optional, List
from pydantic import BaseModel


class GenomeReference(BaseModel):
    """基因组参考配置"""
    id: str
    name: str
    fastaURL: Optional[str] = None
    indexURL: Optional[str] = None
    cytobandURL: Optional[str] = None


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
