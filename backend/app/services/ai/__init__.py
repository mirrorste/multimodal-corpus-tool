"""AI 服务模块 - 低 GPU 依赖架构"""
from app.services.ai.base import AIServiceBase, AIResult
from app.services.ai.llm_provider import LLMProvider
from app.services.ai.vision_provider import VisionProvider
from app.services.ai.ocr_provider import OCRProvider
from app.services.ai.asr_provider import ASRProvider

__all__ = [
    "AIServiceBase",
    "AIResult",
    "LLMProvider",
    "VisionProvider",
    "OCRProvider",
    "ASRProvider",
]