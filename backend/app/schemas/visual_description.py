"""画面描述数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class VisualDescriptionBase(BaseModel):
    description: Optional[str] = None
    objects: Optional[list[Any]] = None  # [{"label": "person", "confidence": 0.95, "bbox": [x,y,w,h]}]
    scene: Optional[str] = None
    emotions: Optional[list[Any]] = None  # [{"label": "happy", "confidence": 0.8}]
    confidence: Optional[float] = None


class VisualDescriptionCreate(VisualDescriptionBase):
    frame_id: str


class VisualDescriptionUpdate(BaseModel):
    description: Optional[str] = None
    objects: Optional[list[Any]] = None
    scene: Optional[str] = None
    emotions: Optional[list[Any]] = None
    confidence: Optional[float] = None


class VisualDescriptionResponse(VisualDescriptionBase):
    id: str
    frame_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ObjectDetection(BaseModel):
    """物体检测结果"""
    label: str
    confidence: float
    bbox: list[float]  # [x, y, width, height]


class SceneClassification(BaseModel):
    """场景分类结果"""
    label: str
    confidence: float


class EmotionDetection(BaseModel):
    """情感检测结果"""
    label: str
    confidence: float


class VisualAnalysisConfig(BaseModel):
    """视觉分析配置"""
    enable_description: bool = True
    enable_object_detection: bool = True
    enable_scene_classification: bool = True
    enable_emotion_detection: bool = False
    description_model: str = "blip2"  # blip2, git, vit-gpt2
    object_detection_model: str = "yolov8"  # yolov8, faster-rcnn