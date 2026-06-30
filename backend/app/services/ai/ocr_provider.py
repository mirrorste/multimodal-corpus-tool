"""OCR 提供方 - 支持本地 PaddleOCR 和云端 API"""
import os
import httpx
import io
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# 可选依赖
try:
    from PIL import Image, ImageEnhance
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    Image = None
    ImageEnhance = None
    logger.warning("Pillow 未安装，OCR 图片预处理功能不可用")


class OCRProvider:
    """OCR 提供方 - 本地 PaddleOCR + 云端 API"""

    def __init__(self):
        self.local_available = self._check_paddleocr()
        self.dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        self.google_key = os.getenv("GOOGLE_VISION_API_KEY")

        self.config = self._auto_config()
        logger.info(
            f"OCR Provider initialized: "
            f"PaddleOCR: {'✓' if self.local_available else '✗'}, "
            f"DashScope: {'✓' if self.dashscope_key else '✗'}, "
            f"Google: {'✓' if self.google_key else '✗'}"
        )

    def _check_paddleocr(self) -> bool:
        """检查 PaddleOCR 是否可用"""
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False

    def _auto_config(self) -> Optional[str]:
        """自动选择配置"""
        if self.dashscope_key:
            return "dashscope"
        elif self.google_key:
            return "google"
        return None

    def is_available(self) -> bool:
        return self.local_available or self.config is not None

    def _image_to_bytes(self, image_path: str) -> bytes:
        """获取图片字节（带可选预处理）"""
        if _PIL_AVAILABLE and Image and ImageEnhance:
            with Image.open(image_path) as img:
                # 预处理：增强对比度
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.2)

                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                return buffer.getvalue()
        else:
            # 无 PIL 时直接读取
            with open(image_path, "rb") as f:
                return f.read()

    async def recognize(self, image_path: str) -> Dict[str, Any]:
        """
        OCR 识别

        Returns:
            {
                "success": bool,
                "text": str,
                "segments": [{"text": str, "bbox": [x1,y1,x2,y2], "confidence": float}],
                "language": str,
                "error": str
            }
        """
        # 优先本地
        if self.local_available:
            result = await self._recognize_local(image_path)
            if result["success"]:
                return result

        # 备选云端
        if self.config == "dashscope":
            return await self._recognize_dashscope(image_path)
        elif self.config == "google":
            return await self._recognize_google(image_path)

        return {
            "success": False,
            "text": None,
            "segments": [],
            "language": None,
            "error": "No OCR method available",
        }

    async def _recognize_local(self, image_path: str) -> Dict[str, Any]:
        """本地 PaddleOCR 识别"""
        try:
            from paddleocr import PaddleOCR

            if not hasattr(self, '_ocr_engine'):
                self._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",  # 中英文
                    use_gpu=False,  # 明确禁用 GPU
                    show_log=False,
                )

            result = self._ocr_engine.ocr(image_path, cls=True)

            if not result or not result[0]:
                return {
                    "success": True,
                    "text": "",
                    "segments": [],
                    "language": "unknown",
                    "provider": "paddleocr-local",
                }

            segments = []
            texts = []
            confidences = []

            for line in result[0]:
                bbox = line[0]
                text = line[1][0]
                confidence = line[1][1]

                # 展平边界框
                flat_bbox = [coord for point in bbox for coord in point]

                segments.append({
                    "text": text,
                    "bbox": flat_bbox,
                    "confidence": confidence,
                })
                texts.append(text)
                confidences.append(confidence)

            return {
                "success": True,
                "text": " ".join(texts),
                "segments": segments,
                "language": self._detect_language("".join(texts)),
                "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
                "provider": "paddleocr-local",
            }

        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return {
                "success": False,
                "text": None,
                "segments": [],
                "language": None,
                "error": str(e),
                "provider": "paddleocr-local",
            }

    async def _recognize_dashscope(self, image_path: str) -> Dict[str, Any]:
        """阿里云 OCR API"""
        try:
            image_bytes = self._image_to_bytes(image_path)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/ocr/text-recognition",
                    headers={
                        "Authorization": f"Bearer {self.dashscope_key}",
                    },
                    files={"file": ("image.png", image_bytes, "image/png")},
                    data={"model": "ocr-api"},
                )

                if response.status_code == 200:
                    data = response.json()
                    output = data.get("output", {})

                    # 解析阿里云 OCR 输出格式
                    text_regions = output.get("text_regions", [])

                    segments = []
                    texts = []

                    for region in text_regions:
                        text = region.get("text", "")
                        texts.append(text)
                        segments.append({
                            "text": text,
                            "bbox": region.get("bbox", []),
                            "confidence": region.get("confidence", 1.0),
                        })

                    return {
                        "success": True,
                        "text": " ".join(texts),
                        "segments": segments,
                        "language": output.get("language", "unknown"),
                        "confidence": output.get("avg_confidence", 0.95),
                        "provider": "dashscope-ocr",
                    }

        except Exception as e:
            logger.error(f"DashScope OCR failed: {e}")
            return {
                "success": False,
                "text": None,
                "segments": [],
                "language": None,
                "error": str(e),
                "provider": "dashscope-ocr",
            }

    async def _recognize_google(self, image_path: str) -> Dict[str, Any]:
        """Google Vision OCR"""
        try:
            import base64
            with open(image_path, "rb") as f:
                image_content = base64.b64encode(f.read()).decode()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://vision.googleapis.com/v1/images:annotate?key={self.google_key}",
                    json={
                        "requests": [{
                            "image": {"content": image_content},
                            "features": [
                                {"type": "TEXT_DETECTION", "maxResults": 100},
                                {"type": "DOCUMENT_TEXT_DETECTION"},
                            ],
                        }]
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    annotations = data["responses"][0]

                    if "textAnnotations" in annotations:
                        segments = []
                        texts = []

                        for ann in annotations["textAnnotations"]:
                            text = ann["description"]
                            bbox = ann["boundingPoly"]["vertices"]
                            flat_bbox = [[v.get("x", 0), v.get("y", 0)] for v in bbox]

                            if len(segments) == 0:
                                # 第一个是完整文本
                                texts.append(text)
                                segments.append({
                                    "text": text,
                                    "bbox": flat_bbox,
                                    "confidence": 1.0,
                                })

                        return {
                            "success": True,
                            "text": texts[0] if texts else "",
                            "segments": segments,
                            "language": "unknown",
                            "confidence": 0.95,
                            "provider": "google-vision",
                        }

        except Exception as e:
            logger.error(f"Google Vision OCR failed: {e}")
            return {
                "success": False,
                "text": None,
                "segments": [],
                "language": None,
                "error": str(e),
                "provider": "google-vision",
            }

    def _detect_language(self, text: str) -> str:
        """简单语言检测"""
        # 统计中文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text)

        if total_chars == 0:
            return "unknown"

        chinese_ratio = chinese_chars / total_chars

        if chinese_ratio > 0.5:
            return "zh"
        elif chinese_ratio > 0.2:
            return "mixed"
        else:
            return "en"


# 全局单例
ocr_provider = OCRProvider()
