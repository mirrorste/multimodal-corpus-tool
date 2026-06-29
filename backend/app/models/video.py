from sqlalchemy import Column, String, Integer, DateTime, Float
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
