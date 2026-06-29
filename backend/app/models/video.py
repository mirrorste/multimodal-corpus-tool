from sqlalchemy import Column, String, Integer, DateTime, Float, Text
from app.core.database import Base
import uuid
from datetime import datetime


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    title = Column(String)
    duration = Column(Integer)
    resolution = Column(String)
    status = Column(String, default="pending")
    file_path = Column(String)
    file_size = Column(Float)
    download_progress = Column(Float, default=0.0)
    downloaded_bytes = Column(Float, default=0.0)
    total_bytes = Column(Float, default=0.0)
    error_message = Column(Text)
    preferred_resolution = Column(String, default="1080p")
    thumbnail_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
