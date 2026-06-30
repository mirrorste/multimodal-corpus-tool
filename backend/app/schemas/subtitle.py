"""字幕数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SubtitleBase(BaseModel):
    start_time: float
    end_time: float
    text: Optional[str] = None
    language: Optional[str] = None
    source: Optional[str] = None  # embedded, OCR, ASR
    confidence: Optional[float] = None


class SubtitleCreate(SubtitleBase):
    video_id: str
    frame_id: Optional[str] = None


class SubtitleUpdate(BaseModel):
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    text: Optional[str] = None
    language: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = None


class SubtitleResponse(SubtitleBase):
    id: str
    video_id: str
    frame_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SubtitleSegment(BaseModel):
    """字幕片段，用于时间轴对齐"""
    start_time: float
    end_time: float
    text: str
    language: str


class SubtitleBatchCreate(BaseModel):
    video_id: str
    subtitles: list[SubtitleBase]