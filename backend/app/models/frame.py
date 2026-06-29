from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey
from app.core.database import Base
import uuid
from datetime import datetime


class Frame(Base):
    __tablename__ = "frames"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    timestamp = Column(Float, nullable=False)
    frame_number = Column(Integer)
    image_path = Column(String)
    has_subtitle = Column(Boolean, default=False)
    quality_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
