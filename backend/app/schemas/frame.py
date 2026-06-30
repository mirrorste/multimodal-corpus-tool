"""帧数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FrameBase(BaseModel):
    timestamp: float
    frame_number: Optional[int] = None
    has_subtitle: Optional[bool] = False
    quality_score: Optional[float] = None


class FrameCreate(FrameBase):
    video_id: str


class FrameUpdate(BaseModel):
    timestamp: Optional[float] = None
    frame_number: Optional[int] = None
    has_subtitle: Optional[bool] = None
    quality_score: Optional[float] = None
    image_path: Optional[str] = None


class FrameResponse(FrameBase):
    id: str
    video_id: str
    image_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FrameBatchCreate(BaseModel):
    video_id: str
    frames: list[FrameBase]