from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class VideoCreate(BaseModel):
    url: str
    platform: str
    preferred_resolution: Optional[str] = "1080p"


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    status: Optional[str] = None
    file_path: Optional[str] = None


class VideoResponse(BaseModel):
    id: str
    url: str
    platform: str
    title: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    status: str
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
