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
    file_size: Optional[float] = None
    download_progress: Optional[float] = None
    downloaded_bytes: Optional[float] = None
    total_bytes: Optional[float] = None
    error_message: Optional[str] = None
    preferred_resolution: Optional[str] = None
    thumbnail_url: Optional[str] = None


class VideoResponse(BaseModel):
    id: str
    url: str
    platform: str
    title: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    status: str
    file_path: Optional[str] = None
    file_size: Optional[float] = None
    download_progress: Optional[float] = None
    downloaded_bytes: Optional[float] = None
    total_bytes: Optional[float] = None
    error_message: Optional[str] = None
    preferred_resolution: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
