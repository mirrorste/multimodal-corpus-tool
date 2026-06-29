from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from app.core.database import Base
import uuid
from datetime import datetime


class AudioSegment(Base):
    __tablename__ = "audio_segments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    audio_path = Column(String)
    asr_text = Column(String)
    language = Column(String)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
