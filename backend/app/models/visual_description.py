from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON
from app.core.database import Base
import uuid
from datetime import datetime


class VisualDescription(Base):
    __tablename__ = "visual_descriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    frame_id = Column(String, ForeignKey("frames.id"), nullable=False)
    description = Column(String)
    objects = Column(JSON)
    scene = Column(String)
    emotions = Column(JSON)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
