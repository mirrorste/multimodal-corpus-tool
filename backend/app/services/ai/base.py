"""AI 服务基类和接口定义"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class AIResult:
    """AI 处理结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    confidence: float = 0.0
    provider: str = "local"
    processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "confidence": self.confidence,
            "provider": self.provider,
            "processing_time": round(self.processing_time, 3),
            "timestamp": self.timestamp.isoformat(),
        }


class AIServiceBase(ABC):
    """AI 服务基类 - 统一接口设计"""

    def __init__(self):
        self.local_available = self._check_local_available()
        self.api_available = self._check_api_available()
        self.config = self._load_config()

        logger.info(
            f"{self.__class__.__name__} initialized - "
            f"Local: {'✓' if self.local_available else '✗'}, "
            f"API: {'✓' if self.api_available else '✗'}"
        )

    @abstractmethod
    def _check_local_available(self) -> bool:
        """检查本地模型是否可用"""
        pass

    @abstractmethod
    def _check_api_available(self) -> bool:
        """检查 API 是否可用"""
        pass

    def _load_config(self) -> Dict:
        """加载配置"""
        return {
            "prefer_local": os.getenv("PREFER_LOCAL", "true").lower() == "true",
            "fallback_to_api": os.getenv("FALLBACK_TO_API", "true").lower() == "true",
            "local_only": os.getenv("LOCAL_ONLY", "false").lower() == "true",
        }

    @abstractmethod
    async def process_local(self, *args, **kwargs) -> AIResult:
        """本地处理"""
        pass

    @abstractmethod
    async def process_api(self, *args, **kwargs) -> AIResult:
        """API 处理"""
        pass

    async def process(self, *args, **kwargs) -> AIResult:
        """统一处理入口 - 支持降级策略"""
        import time
        start_time = time.time()

        prefer_local = self.config.get("prefer_local", True)
        fallback_to_api = self.config.get("fallback_to_api", True)
        local_only = self.config.get("local_only", False)

        # 策略 1: 仅本地模式
        if local_only:
            result = await self.process_local(*args, **kwargs)
            result.processing_time = time.time() - start_time
            return result

        # 策略 2: 优先本地
        if prefer_local and self.local_available:
            result = await self.process_local(*args, **kwargs)
            if result.success:
                result.processing_time = time.time() - start_time
                return result

            # 本地失败，尝试 API
            if fallback_to_api and self.api_available:
                result = await self.process_api(*args, **kwargs)
                result.processing_time = time.time() - start_time
                return result

            result.processing_time = time.time() - start_time
            return result

        # 策略 3: 优先 API
        if self.api_available:
            result = await self.process_api(*args, **kwargs)
            result.processing_time = time.time() - start_time
            return result

        # 策略 4: 最后尝试本地
        if self.local_available:
            result = await self.process_local(*args, **kwargs)
            result.processing_time = time.time() - start_time
            return result

        # 都失败
        return AIResult(
            success=False,
            error="No processing method available",
            provider="none",
            processing_time=time.time() - start_time,
        )

    def is_available(self) -> Dict[str, bool]:
        """获取可用性状态"""
        return {
            "local": self.local_available,
            "api": self.api_available,
            "any": self.local_available or self.api_available,
        }
