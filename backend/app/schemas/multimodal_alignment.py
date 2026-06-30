"""多模态对齐数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MultimodalAlignmentBase(BaseModel):
    timestamp: float
    subtitle_id: Optional[str] = None
    audio_segment_id: Optional[str] = None
    frame_id: Optional[str] = None
    visual_description_id: Optional[str] = None
    alignment_score: Optional[float] = None


class MultimodalAlignmentCreate(MultimodalAlignmentBase):
    video_id: str


class MultimodalAlignmentUpdate(BaseModel):
    timestamp: Optional[float] = None
    subtitle_id: Optional[str] = None
    audio_segment_id: Optional[str] = None
    frame_id: Optional[str] = None
    visual_description_id: Optional[str] = None
    alignment_score: Optional[float] = None


class MultimodalAlignmentResponse(MultimodalAlignmentBase):
    id: str
    video_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AlignmentResult(BaseModel):
    """单条对齐结果"""
    timestamp: float
    subtitle_text: Optional[str] = None
    subtitle_language: Optional[str] = None
    asr_text: Optional[str] = None
    asr_language: Optional[str] = None
    visual_description: Optional[str] = None
    objects: Optional[list] = None
    scene: Optional[str] = None
    alignment_score: float


class AlignmentConfig(BaseModel):
    """对齐配置"""
    time_tolerance: float = 0.5  # 时间容差（秒）
    semantic_threshold: float = 0.7  # 语义相似度阈值
    enable_semantic_alignment: bool = True  # 是否启用语义对齐