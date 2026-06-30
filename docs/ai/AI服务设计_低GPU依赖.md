# AI 模型服务 - 低 GPU 依赖架构设计

**版本**: v1.0
**更新日期**: 2026-06-30
**目标**: 最小化 GPU 依赖，主要依赖 CPU 和云端 API

---

## 一、架构设计原则

### 1.1 核心原则

| 原则 | 说明 |
|------|------|
| **本地优先** | 优先使用本地 CPU 模型 |
| **API 兜底** | 本地无法处理时调用云端 API |
| **成本可控** | 使用免费/低成本 API |
| **异步处理** | 所有 AI 处理异步执行，不阻塞主流程 |

### 1.2 模型选择策略

```
┌─────────────────────────────────────────────────────────────┐
│                     任务类型                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  简单任务（高频） ──────► 本地模型处理                      │
│  例：OCR、物体检测、基础 ASR                                 │
│                                                             │
│  复杂任务（中频） ──────► 云端 API 处理                      │
│  例：图像描述、复杂语义分析                                   │
│                                                             │
│  批量任务（低频） ──────► 批量 API 处理                      │
│  例：大规模语料分析                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、AI 服务模块

### 2.1 服务架构

```
backend/app/services/ai/
├── __init__.py                 # 模块导出
├── base.py                     # AI服务基类和接口定义
├── llm_provider.py            # LLM提供商（DeepSeek/OpenAI/阿里云）
├── vision_provider.py         # 视觉分析（YOLOv8n + 云端API）
├── ocr_provider.py            # OCR服务（PaddleOCR + 云端API）
└── asr_provider.py            # ASR服务（Whisper CPU模式）

backend/app/services/
├── metaphor_service.py         # 隐喻识别服务（规则引擎 + LLM）
└── untranslatability_service.py # 不可译性服务（规则引擎 + LLM）
```

### 2.2 基类定义

```python
# backend/app/services/ai/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AIResult:
    """AI 处理结果基类"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    confidence: float = 0.0
    provider: str = "local"
    processing_time: float = 0.0


class AIServiceBase(ABC):
    """AI 服务基类"""

    def __init__(self):
        self.local_available = self._check_local_available()
        self.api_available = self._check_api_available()
        logger.info(f"{self.__class__.__name__} - Local: {self.local_available}, API: {self.api_available}")

    @abstractmethod
    def _check_local_available(self) -> bool:
        """检查本地模型是否可用"""
        pass

    @abstractmethod
    def _check_api_available(self) -> bool:
        """检查 API 是否可用"""
        pass

    @abstractmethod
    async def process_local(self, input_data: Any) -> AIResult:
        """本地处理"""
        pass

    @abstractmethod
    async def process_api(self, input_data: Any) -> AIResult:
        """API 处理"""
        pass

    async def process(
        self,
        input_data: Any,
        prefer_local: bool = True,
        fallback_to_api: bool = True,
    ) -> AIResult:
        """统一处理入口"""
        import time
        start_time = time.time()

        # 优先本地
        if prefer_local and self.local_available:
            result = await self.process_local(input_data)
            if result.success:
                result.processing_time = time.time() - start_time
                return result

        # 降级到 API
        if fallback_to_api and self.api_available:
            result = await self.process_api(input_data)
            result.processing_time = time.time() - start_time
            return result

        # 都失败
        return AIResult(
            success=False,
            error="Both local and API processing failed",
            provider="none",
            processing_time=time.time() - start_time,
        )
```

---

## 三、OCR 服务

### 3.1 模型选择

| 方案 | 模型 | GPU | 速度 | 准确性 | 费用 |
|------|------|-----|------|--------|------|
| **本地（推荐）** | PaddleOCR-lite | ❌ | ~10 img/s | 92% | $0 |
| 本地备选 | EasyOCR | ❌ | ~5 img/s | 88% | $0 |
| API | Google Vision OCR | - | 快 | 96% | 免费额度 |

### 3.2 实现

```python
# backend/app/services/ai/ocr_service.py

import asyncio
from typing import Optional
from PIL import Image
from .base import AIServiceBase, AIResult

logger = logging.getLogger(__name__)


class OCRService(AIServiceBase):
    """OCR 服务 - 支持本地和 API"""

    def __init__(self):
        self.local_engine = None
        self.api_key = os.getenv("GOOGLE_VISION_API_KEY")
        super().__init__()

    def _check_local_available(self) -> bool:
        """检查 PaddleOCR 是否可用"""
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            logger.warning("PaddleOCR 未安装")
            return False

    def _check_api_available(self) -> bool:
        """检查 API 是否可用"""
        return bool(self.api_key) or bool(os.getenv("DASHSCOPE_API_KEY"))

    async def process_local(self, image_path: str) -> AIResult:
        """本地 PaddleOCR 处理"""
        try:
            from paddleocr import PaddleOCR

            if self.local_engine is None:
                self.local_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",  # 中英文
                    use_gpu=False,  # 明确禁用 GPU
                    show_log=False,
                )

            result = self.local_engine.ocr(image_path, cls=True)

            if not result or not result[0]:
                return AIResult(success=True, data=[], confidence=0.0)

            # 解析结果
            texts = []
            confidences = []
            for line in result[0]:
                texts.append(line[1][0])
                confidences.append(line[1][1])

            return AIResult(
                success=True,
                data={
                    "text": " ".join(texts),
                    "segments": [
                        {"text": t, "confidence": c}
                        for t, c in zip(texts, confidences)
                    ],
                },
                confidence=sum(confidences) / len(confidences) if confidences else 0.0,
                provider="paddleocr-local",
            )

        except Exception as e:
            logger.error(f"PaddleOCR 处理失败: {e}")
            return AIResult(success=False, error=str(e))

    async def process_api(self, image_path: str) -> AIResult:
        """云端 OCR API 处理"""
        # 优先使用阿里云 OCR（免费额度大）
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if api_key:
            return await self._process_dashscope_ocr(image_path, api_key)

        # 备选 Google Vision
        if self.api_key:
            return await self._process_google_vision(image_path, self.api_key)

        return AIResult(success=False, error="No OCR API available")

    async def _process_dashscope_ocr(self, image_path: str, api_key: str) -> AIResult:
        """阿里云 OCR"""
        import httpx

        with open(image_path, "rb") as f:
            image_data = f.read()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/ocr/text-recognition",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"image": ("image.jpg", image_data, "image/jpeg")},
                data={"model": "ocr-api"},
            )

        if response.status_code == 200:
            data = response.json()
            return AIResult(
                success=True,
                data=data.get("output", {}),
                confidence=0.95,
                provider="dashscope-ocr",
            )

        return AIResult(success=False, error=f"API error: {response.status_code}")
```

---

## 四、ASR 服务

### 4.1 模型选择

| 方案 | 模型 | GPU | 速度 | 准确性 | 费用 |
|------|------|-----|------|--------|------|
| **本地（推荐）** | Whisper tiny/base | ⚠️ 推荐 | ~1x | 80-85% | $0 |
| 本地备选 | Whisper small | ✅ 需要 | ~4x | 90-93% | $0 |
| API | 阿里云 ASR | - | 快 | 95% | 免费额度 |

### 4.2 实现

```python
# backend/app/services/ai/asr_service.py

import asyncio
import whisper
from .base import AIServiceBase, AIResult


class ASRService(AIServiceBase):
    """ASR 服务 - Whisper 本地 + 云端 API"""

    def __init__(self):
        self.model = None
        self.model_name = os.getenv("WHISPER_MODEL", "base")  # tiny/base/small
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        super().__init__()

    def _check_local_available(self) -> bool:
        """检查 Whisper 是否可用"""
        try:
            import whisper
            return True
        except ImportError:
            logger.warning("Whisper 未安装")
            return False

    def _check_api_available(self) -> bool:
        return bool(self.api_key)

    async def process_local(self, audio_path: str) -> AIResult:
        """本地 Whisper 处理"""
        try:
            # 加载模型（首次加载）
            if self.model is None:
                self.model = await asyncio.to_thread(
                    whisper.load_model,
                    self.model_name,
                    device="cpu",  # 明确使用 CPU
                )
                logger.info(f"Whisper 模型加载完成: {self.model_name}")

            # 执行转录
            result = await asyncio.to_thread(
                self.model.transcribe,
                audio_path,
                language=None,  # 自动检测
                fp16=False,  # 禁用 FP16（CPU）
                verbose=False,
            )

            return AIResult(
                success=True,
                data={
                    "text": result["text"],
                    "segments": result["segments"],
                    "language": result.get("language", "unknown"),
                },
                confidence=0.9,
                provider=f"whisper-{self.model_name}-cpu",
            )

        except Exception as e:
            logger.error(f"Whisper 处理失败: {e}")
            return AIResult(success=False, error=str(e))

    async def process_api(self, audio_path: str) -> AIResult:
        """云端 ASR API"""
        if self.api_key:
            return await self._process_dashscope_asr(audio_path, self.api_key)

        return AIResult(success=False, error="No ASR API available")

    async def _process_dashscope_asr(self, audio_path: str, api_key: str) -> AIResult:
        """阿里云 ASR"""
        import httpx

        async with httpx.AsyncClient() as client:
            # 阿里云语音识别 API
            response = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/audio/asr",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": open(audio_path, "rb")},
                data={"model": "paraformer-zh"},
            )

        if response.status_code == 200:
            data = response.json()
            return AIResult(
                success=True,
                data=data.get("output", {}),
                confidence=0.95,
                provider="dashscope-asr",
            )

        return AIResult(success=False, error=f"API error: {response.status_code}")
```

---

## 五、视觉分析服务

### 5.1 模型选择

| 任务 | 本地方案（CPU） | API 方案 | 备注 |
|------|----------------|----------|------|
| **图像描述** | ❌ 不支持 | 阿里云/腾讯云 | 参数量太大 |
| **物体检测** | YOLOv8n (tiny) | 腾讯云 | 轻量版可选 |
| **场景分类** | MobileNet/ResNet18 | 阿里云 | 小模型可选 |

### 5.2 实现

```python
# backend/app/services/ai/vision_service.py

import asyncio
from .base import AIServiceBase, AIResult


class VisionService(AIServiceBase):
    """视觉分析服务 - 主要依赖 API"""

    def __init__(self):
        self.detector = None
        self.classifier = None
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.tencent_secret_id = os.getenv("TENCENT_SECRET_ID")
        self.tencent_secret_key = os.getenv("TENCENT_SECRET_KEY")
        super().__init__()

    def _check_local_available(self) -> bool:
        """只有物体检测可用本地"""
        try:
            import torch
            import torchvision
            return True
        except ImportError:
            return False

    def _check_api_available(self) -> bool:
        return bool(self.api_key or (self.tencent_secret_id and self.tencent_secret_key))

    async def generate_description(self, image_path: str) -> AIResult:
        """生成图像描述 - 只能使用 API"""
        if self.api_key:
            return await self._process_dashscope_vlp(image_path, self.api_key)

        # 返回占位结果
        return AIResult(
            success=True,
            data={"description": "图像描述（需配置 API）"},
            confidence=0.0,
            provider="placeholder",
        )

    async def detect_objects(self, image_path: str) -> AIResult:
        """物体检测 - 本地或 API"""
        result = await self.process(image_path, prefer_local=True)
        return result

    async def process_local(self, image_path: str) -> AIResult:
        """本地物体检测 - 使用 YOLOv8n"""
        try:
            from ultralytics import YOLO

            if self.detector is None:
                # 加载最小的 YOLOv8n 模型
                self.detector = YOLO("yolov8n.pt")  # nano 版本，~6MB

            results = await asyncio.to_thread(
                self.detector.predict,
                image_path,
                conf=0.25,
                iou=0.45,
            )

            objects = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    objects.append({
                        "label": result.names[int(box.cls[0])],
                        "confidence": float(box.conf[0]),
                        "bbox": box.xyxy[0].tolist(),
                    })

            return AIResult(
                success=True,
                data={"objects": objects},
                confidence=0.85,
                provider="yolov8n-cpu",
            )

        except Exception as e:
            logger.error(f"YOLOv8 处理失败: {e}")
            return AIResult(success=False, error=str(e))

    async def process_api(self, image_path: str) -> AIResult:
        """云端视觉 API"""
        if self.api_key:
            return await self._process_dashscope_vlp(image_path, self.api_key)

        return AIResult(success=False, error="No Vision API available")
```

---

## 六、隐喻识别服务

> 实际代码位置：`backend/app/services/metaphor_service.py`

### 6.1 模型选择

| 方案 | 模型 | GPU | 准确性 | 费用 |
|------|------|-----|--------|------|
| **本地（规则）** | 关键词匹配 | ❌ | 40-50% | $0 |
| **API（推荐）** | DeepSeek/ GPT-4o-mini | ❌ | 85-90% | ~$0.001/次 |

### 6.2 混合检测流程

```python
async def detect_metaphors(self, text: str, use_llm: bool = True, language: str = "zh"):
    """混合检测：规则引擎 + LLM API"""

    # 1. 先用规则引擎（快速，零成本）
    rule_results = self._detect_with_rules(text)

    # 2. 如果需要且可用，再用 LLM
    if use_llm and self.is_llm_available():
        llm_results = await self._detect_with_llm(text, language)

    # 3. 合并结果并去重
    return merged_results
```

### 6.3 预定义隐喻模式

```python
COMMON_METAPHORS = {
    "TIME_IS_MONEY": {
        "source": "money",
        "target": "time",
        "keywords": ["花费", "浪费", "节约", "投资"],
    },
    "LIFE_IS_JOURNEY": {
        "source": "journey",
        "target": "life",
        "keywords": ["路", "旅程", "起点", "终点"],
    },
    # ... 更多 Lakoff & Johnson 概念隐喻
}
```

---

## 七、不可译性识别服务

> 实际代码位置：`backend/app/services/untranslatability_service.py`

### 7.1 模型选择

| 方案 | 模型 | GPU | 准确性 | 费用 |
|------|------|-----|--------|------|
| **本地（规则）** | 文化专有项词典 + 规则 | ❌ | 50-60% | $0 |
| **API（推荐）** | DeepSeek/ GPT-4o-mini | ❌ | 85-90% | ~$0.001/次 |

### 7.2 不可译类型

```python
# 语言层面
LINGUISTIC_UNTRANSLATABLE = {
    "phonological": ["pun", "谐音", "双关"],
    "morphological": ["复合词", "派生词"],
    "syntactic": ["话题-评论结构"],
    "semantic": ["词汇空缺", "多义词"],
}

# 文化层面
CULTURAL_SPECIFIC_ITEMS = {
    "zh": {
        "idioms": ["龙", "凤", "春节", "功夫"],
        "social_terms": ["面子", "人情", "关系"],
    },
    "en": {
        "idioms": ["break a leg", "piece of cake"],
        "cultural_refs": ["Thanksgiving", "super bowl"],
    },
}

# 语境层面
CONTEXTUAL_UNTRANSLATABLE = {
    "discourse": ["衔接手段", "言语行为"],
    "pragmatic": ["隐含意义", "预设"],
    "intercultural": ["禁忌", "礼貌策略"],
}
```

### 7.3 混合检测流程

```python
async def detect_untranslatability(
    self,
    text: str,
    source_language: str = "en",
    target_language: str = "zh",
    use_llm: bool = True,
) -> Dict[str, Any]:
    """混合检测：规则引擎 + LLM API"""

    # 1. 规则引擎检测（快速）
    rule_results = self._detect_with_rules(text, source_language)

    # 2. LLM API 检测（如可用）
    if use_llm and self.is_llm_available():
        llm_results = await self._detect_with_llm(text, source_language, target_language)

    # 3. 合并去重
    return merged_results
```

---

## 八、LLM 提供商配置

### 8.1 支持的提供商

| 提供商 | API Key 环境变量 | 模型 | 费用 |
|--------|------------------|------|------|
| DeepSeek | DEEPSEEK_API_KEY | deepseek-chat | ~$0.001/1K tokens |
| OpenAI | OPENAI_API_KEY | gpt-4o-mini | ~$0.005/1K tokens |
| 阿里云 | DASHSCOPE_API_KEY | qwen-turbo | 免费额度 |

### 8.2 配置示例 (.env)

```bash
# AI 服务配置（低 GPU 依赖架构）
# 优先使用本地模型，API 作为降级方案

# LLM API Keys（至少配置一个）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LLM 模型选择（可选，默认自动选择）
# DEEPSEEK_MODEL=deepseek-chat
# OPENAI_MODEL=gpt-4o-mini
# DASHSCOPE_MODEL=qwen-turbo

# Whisper 模型（CPU 模式）
WHISPER_MODEL=base

# 本地优先策略
# true: 优先使用本地模型，API 作为降级
# false: 优先使用 API，本地作为降级
PREFER_LOCAL=true

# 视觉分析 Provider
# local: 仅使用本地 YOLOv8n（轻量GPU/CPU）
# api: 仅使用云端 API
# hybrid: 混合模式（推荐）
VISION_PROVIDER=hybrid

# OCR Provider
OCR_PROVIDER=hybrid
```

---

## 九、成本估算（无 GPU）

### 9.1 月度成本（100 个视频，每个 5 分钟）

| 任务 | 本地处理 | API 调用 | 估算费用 |
|------|----------|----------|----------|
| OCR | ~100 分钟 | 少量 | $0 |
| ASR | ~500 分钟 | 少量 | $0 |
| 物体检测 | ~50 分钟 | 少量 | $0 |
| 图像描述 | 0 | ~500 次 | $0-5 |
| 隐喻识别 | 规则 | ~500 次 | $0.5-2 |
| 不可译性 | 规则 | ~500 次 | $0.5-2 |
| **总计** | | | **$1-9/月** |

### 9.2 优化建议

1. **优先本地**：OCR、ASR、物体检测使用本地模型
2. **API 降级**：复杂任务先本地规则，必要时调用 API
3. **批量优惠**：大量处理时申请 API 企业优惠

---

## 十、部署要求

### 10.1 CPU 部署

```yaml
# docker-compose.yml
services:
  api:
    image: multimodal-corpus:latest
    environment:
      - WHISPER_MODEL=base  # 使用小模型
    deploy:
      resources:
        limits:
          cpus: '4'  # 限制 CPU
          memory: 8G
```

### 10.2 推荐配置

| 环境 | CPU | 内存 | 存储 | GPU |
|------|-----|------|------|-----|
| 开发 | 4 核 | 8GB | 100GB | ❌ |
| 小规模 | 8 核 | 16GB | 500GB | ❌ |
| 中规模 | 16 核 | 32GB | 1TB | ⚠️ 可选 |
| 生产 | 32+ 核 | 64GB+ | 2TB+ | ⚠️ 推荐 |

---

*AI 服务设计文档 - 低 GPU 依赖架构*
