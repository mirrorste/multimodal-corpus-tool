from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from app.core.database import Base
import uuid
from datetime import datetime


class UntranslatabilityAnnotation(Base):
    __tablename__ = "untranslatability_annotations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    alignment_id = Column(String, ForeignKey("multimodal_alignments.id"), nullable=False)
    type = Column(String)
    category = Column(String)
    description = Column(String)
    severity = Column(Integer)
    confidence = Column(Float)
    annotator = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
