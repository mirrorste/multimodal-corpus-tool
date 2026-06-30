"""不可译性标注数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UntranslatabilityAnnotationBase(BaseModel):
    type: Optional[str] = None  # linguistic, cultural, contextual
    category: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None  # 1-5
    confidence: Optional[float] = None
    annotator: Optional[str] = None  # auto, manual


class UntranslatabilityAnnotationCreate(UntranslatabilityAnnotationBase):
    alignment_id: str


class UntranslatabilityAnnotationUpdate(BaseModel):
    type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None
    confidence: Optional[float] = None
    annotator: Optional[str] = None


class UntranslatabilityAnnotationResponse(UntranslatabilityAnnotationBase):
    id: str
    alignment_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class UntranslatabilityType(BaseModel):
    """不可译性类型定义"""
    type: str
    category: str
    description: str
    severity_range: tuple[int, int]
    examples: list[str]


class LinguisticUntranslatability(BaseModel):
    """语言层面不可译性"""
    category: str  # phonological, morphological, syntactic, semantic
    source_text: str
    issue_description: str
    translation_options: Optional[list[str]] = None
    severity: int


class CulturalUntranslatability(BaseModel):
    """文化层面不可译性"""
    category: str  # cultural_specific_item, idiom, metaphor, reference
    source_text: str
    cultural_context: str
    target_culture_equivalence: Optional[str] = None
    translation_strategy: Optional[str] = None
    severity: int


class ContextualUntranslatability(BaseModel):
    """语境层面不可译性"""
    category: str  # discourse, pragmatic, register
    source_text: str
    context_description: str
    missing_context: list[str]
    severity: int