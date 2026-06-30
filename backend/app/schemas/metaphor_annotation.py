"""隐喻标注数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MetaphorAnnotationBase(BaseModel):
    type: Optional[str] = None  # conceptual, visual, multimodal
    source_domain: Optional[str] = None
    target_domain: Optional[str] = None
    trigger: Optional[str] = None
    confidence: Optional[float] = None
    annotator: Optional[str] = None  # auto, manual


class MetaphorAnnotationCreate(MetaphorAnnotationBase):
    alignment_id: str


class MetaphorAnnotationUpdate(BaseModel):
    type: Optional[str] = None
    source_domain: Optional[str] = None
    target_domain: Optional[str] = None
    trigger: Optional[str] = None
    confidence: Optional[float] = None
    annotator: Optional[str] = None


class MetaphorAnnotationResponse(MetaphorAnnotationBase):
    id: str
    alignment_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class MetaphorType(BaseModel):
    """隐喻类型定义"""
    type: str
    source_domain: str
    target_domain: str
    description: str
    examples: list[str]


class ConceptualMetaphor(BaseModel):
    """概念隐喻"""
    source_domain: str
    target_domain: str
    linguistic_expression: str
    context: Optional[str] = None


class VisualMetaphor(BaseModel):
    """视觉隐喻"""
    visual_element: str
    conceptual_mapping: str
    source_domain: str
    target_domain: str


class MultimodalMetaphor(BaseModel):
    """多模态隐喻"""
    text_trigger: Optional[str] = None
    visual_trigger: Optional[str] = None
    source_domain: str
    target_domain: str
    modality_interaction: str  # reinforcement, extension, contradiction