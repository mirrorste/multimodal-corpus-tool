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
├── __init__.py
├── base.py                    # 基类和接口定义
├── ocr_service.py             # OCR 服务
├── asr_service.py            # ASR 服务
├── vision_service.py          # 视觉分析服务
├── nlp_service.py            # NLP 服务
├── metaphor_service.py        # 隐喻识别服务
├── untrans_service.py        # 不可译性服务
└── llm_provider.py           # LLM 提供商
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

### 6.1 模型选择

| 方案 | 模型 | GPU | 准确性 | 费用 |
|------|------|-----|--------|------|
| **本地（规则）** | 关键词匹配 | ❌ | 40-50% | $0 |
| **本地（小型模型）** | BERT-base-chinese | ⚠️ 可选 | 70-75% | $0 |
| **API（推荐）** | GPT-4o-mini/DeepSeek | ❌ | 85-90% | ~$0.001/次 |

### 6.2 实现

```python
# backend/app/services/ai/metaphor_service.py

from .base import AIServiceBase, AIResult


class MetaphorService(AIServiceBase):
    """隐喻识别服务 - 规则引擎 + LLM API"""

    def __init__(self):
        self.llm_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.llm_provider = self._detect_provider()
        super().__init__()

    def _check_local_available(self) -> bool:
        """规则引擎始终可用"""
        return True

    def _check_api_available(self) -> bool:
        return bool(self.llm_api_key)

    def _detect_provider(self) -> str:
        if os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek"
        elif os.getenv("OPENAI_API_KEY"):
            return "openai"
        return "none"

    async def process_local(self, text: str) -> AIResult:
        """本地规则引擎处理"""
        metaphors = self._rule_based_detection(text)

        return AIResult(
            success=True,
            data={"metaphors": metaphors},
            confidence=0.45,  # 规则引擎置信度较低
            provider="rule-engine",
        )

    async def process_api(self, text: str) -> AIResult:
        """LLM API 处理"""
        if self.llm_provider == "deepseek":
            return await self._process_deepseek(text)
        elif self.llm_provider == "openai":
            return await self._process_openai(text)

        return AIResult(success=False, error="No LLM API available")

    def _rule_based_detection(self, text: str) -> list:
        """基于规则的隐喻检测"""
        metaphors = []

        # 预定义隐喻模式
        patterns = {
            "TIME_IS_MONEY": {
                "keywords": ["花费", "浪费", "节约", "投资"],
                "source": "money",
                "target": "time",
            },
            "LIFE_IS_JOURNEY": {
                "keywords": ["路", "道路", "旅程", "起点", "终点"],
                "source": "journey",
                "target": "life",
            },
            # ... 更多模式
        }

        for metaphor_id, pattern in patterns.items():
            for keyword in pattern["keywords"]:
                if keyword in text:
                    metaphors.append({
                        "type": "conceptual",
                        "metaphor_id": metaphor_id,
                        "source_domain": pattern["source"],
                        "target_domain": pattern["target"],
                        "trigger": keyword,
                        "confidence": 0.5,
                    })

        return metaphors

    async def _process_deepseek(self, text: str) -> AIResult:
        """DeepSeek API 隐喻识别"""
        import httpx

        prompt = f"""分析以下文本中的隐喻表达：

文本：{text}

请以 JSON 格式返回：
{{
    "metaphors": [
        {{
            "type": "conceptual|visual|multimodal",
            "source_domain": "源域",
            "target_domain": "目标域",
            "trigger": "触发词/表达",
            "confidence": 0.0-1.0
        }}
    ]
}}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            import json
            result = json.loads(content)

            return AIResult(
                success=True,
                data=result,
                confidence=0.88,
                provider="deepseek",
            )

        return AIResult(success=False, error=f"API error: {response.status_code}")

    async def _process_openai(self, text: str) -> AIResult:
        """OpenAI API 隐喻识别"""
        # 类似 DeepSeek 实现
        pass
```

---

## 七、不可译性识别服务

### 7.1 实现

```python
# backend/app/services/ai/untrans_service.py

from .base import AIServiceBase, AIResult


class UntransService(AIServiceBase):
    """不可译性识别服务"""

    def __init__(self):
        self.llm_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        super().__init__()

    def _check_local_available(self) -> bool:
        return True  # 词典始终可用

    def _check_api_available(self) -> bool:
        return bool(self.llm_api_key)

    async def process_local(self, text: str, source_lang: str, target_lang: str) -> AIResult:
        """本地词典 + 规则"""
        items = self._rule_based_detection(text, source_lang)

        return AIResult(
            success=True,
            data={"items": items},
            confidence=0.55,
            provider="rule-engine",
        )

    async def process_api(self, text: str, source_lang: str, target_lang: str) -> AIResult:
        """LLM API 处理"""
        provider = "deepseek" if os.getenv("DEEPSEEK_API_KEY") else "openai"

        prompt = f"""分析以下文本中翻译困难的内容：

源语言：{source_lang}
目标语言：{target_lang}
文本：{text}

请识别以下类型的不可译现象：
1. 语言层面（语音、词汇、句法、语义）
2. 文化层面（文化专有项、习语、典故）
3. 语境层面（需要上下文理解）

请以 JSON 格式返回：
{{
    "items": [
        {{
            "type": "linguistic|cultural|contextual",
            "category": "具体类别",
            "text": "原文片段",
            "description": "不可译原因",
            "severity": 1-5,
            "translation_options": ["可能的翻译方案"]
        }}
    ]
}}"""

        # 调用 LLM API（类似 MetaphorService）
        result = await self._call_llm(prompt)

        if result.success:
            result.provider = provider

        return result
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
# AI 服务配置
# ====================

# Whisper 模型（CPU 可用：tiny/base/small）
WHISPER_MODEL=base

# OCR API（可选）
# 阿里云 - 免费额度大
DASHSCOPE_API_KEY=sk-xxxxxxxx

# LLM API（用于复杂语义分析）
# DeepSeek - 性价比高（推荐）
DEEPSEEK_API_KEY=sk-xxxxxxxx

# 或 OpenAI（备用）
# OPENAI_API_KEY=sk-xxxxxxxx

# 视觉 API（可选）
TENCENT_SECRET_ID=xxxxxxxx
TENCENT_SECRET_KEY=xxxxxxxx

# 处理策略
PREFER_LOCAL=true          # 优先使用本地模型
FALLBACK_TO_API=true       # 本地失败时调用 API
LOCAL_ONLY=false           # 仅使用本地（离线模式）
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
