"""语料输出数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class VideoInfo(BaseModel):
    """视频信息"""
    id: str
    url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    platform: str


class TimelineEntry(BaseModel):
    """时间轴条目"""
    timestamp: float
    subtitle: Optional[dict] = None  # {"text": "...", "language": "en", "source": "OCR"}
    audio: Optional[dict] = None  # {"asr_text": "...", "language": "en"}
    visual: Optional[dict] = None  # {"description": "...", "objects": [], "scene": "..."}
    annotations: Optional[dict] = None  # {"metaphors": [], "untranslatability": []}


class CorpusOutput(BaseModel):
    """语料输出"""
    video_info: VideoInfo
    timeline: list[TimelineEntry]
    metadata: Optional[dict] = None


class CorpusExportConfig(BaseModel):
    """语料导出配置"""
    format: str = "json"  # json, csv, xml
    include_subtitles: bool = True
    include_audio: bool = True
    include_visual: bool = True
    include_annotations: bool = True
    time_unit: str = "seconds"  # seconds, milliseconds
    language_filter: Optional[list[str]] = None  # 只包含指定语言


class CorpusStatistics(BaseModel):
    """语料统计"""
    video_count: int
    total_duration: float
    subtitle_count: int
    audio_segment_count: int
    frame_count: int
    alignment_count: int
    metaphor_count: int
    untranslatability_count: int
    languages: dict[str, int]  # {"en": 100, "zh": 50}
    metaphor_types: dict[str, int]  # {"conceptual": 20, "visual": 10, "multimodal": 5}
    untranslatability_types: dict[str, int]  # {"linguistic": 15, "cultural": 25, "contextual": 5}


class CorpusQuery(BaseModel):
    """语料查询参数"""
    video_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    language: Optional[str] = None
    has_metaphor: Optional[bool] = None
    has_untranslatability: Optional[bool] = None
    metaphor_type: Optional[str] = None
    untranslatability_type: Optional[str] = None
    keyword: Optional[str] = None


class CorpusBatchExport(BaseModel):
    """批量导出"""
    video_ids: list[str]
    config: CorpusExportConfig
    output_path: Optional[str] = None