from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from app.core.database import Base
import uuid
from datetime import datetime


class MultimodalAlignment(Base):
    __tablename__ = "multimodal_alignments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    timestamp = Column(Float, nullable=False)
    subtitle_id = Column(String, ForeignKey("subtitles.id"))
    audio_segment_id = Column(String, ForeignKey("audio_segments.id"))
    frame_id = Column(String, ForeignKey("frames.id"))
    visual_description_id = Column(String, ForeignKey("visual_descriptions.id"))
    alignment_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
