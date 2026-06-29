from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from app.core.database import Base
import uuid
from datetime import datetime


class Subtitle(Base):
    __tablename__ = "subtitles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    frame_id = Column(String, ForeignKey("frames.id"))
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(String)
    language = Column(String)
    source = Column(String)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
