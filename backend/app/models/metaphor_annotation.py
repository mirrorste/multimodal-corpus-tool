from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from app.core.database import Base
import uuid
from datetime import datetime


class MetaphorAnnotation(Base):
    __tablename__ = "metaphor_annotations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    alignment_id = Column(String, ForeignKey("multimodal_alignments.id"), nullable=False)
    type = Column(String)
    source_domain = Column(String)
    target_domain = Column(String)
    trigger = Column(String)
    confidence = Column(Float)
    annotator = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
