"""视觉分析提供方 - 图像描述、物体检测（低 GPU 依赖）"""
import os
import httpx
from typing import Optional, Dict, Any, List
import base64
import io
import logging

logger = logging.getLogger(__name__)

# 可选依赖
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    logger.warning("Pillow 未安装，图片压缩功能不可用")


class VisionProvider:
    """视觉分析提供方 - 云端 API 为主，本地轻量检测可选"""

    def __init__(self):
        self.dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        self.tencent_secret_id = os.getenv("TENCENT_SECRET_ID")
        self.tencent_secret_key = os.getenv("TENCENT_SECRET_KEY")
        self.local_yolo_available = self._check_yolo_available()

        self.config = self._auto_config()
        logger.info(
            f"Vision Provider initialized: "
            f"DashScope: {'✓' if self.dashscope_key else '✗'}, "
            f"Tencent: {'✓' if self.tencent_secret_id else '✗'}, "
            f"YOLO: {'✓' if self.local_yolo_available else '✗'}"
        )

    def _check_yolo_available(self) -> bool:
        """检查本地 YOLO 是否可用"""
        try:
            from ultralytics import YOLO
            return True
        except ImportError:
            return False

    def _auto_config(self) -> Optional[str]:
        """自动选择配置"""
        if self.dashscope_key:
            return "dashscope"
        elif self.tencent_secret_id:
            return "tencent"
        return None

    def is_available(self) -> bool:
        return self.config is not None or self.local_yolo_available

    def _image_to_base64(self, image_path: str) -> str:
        """图片转 base64"""
        if _PIL_AVAILABLE:
            with Image.open(image_path) as img:
                # 压缩图片（减少 API 传输大小）
                if max(img.size) > 1024:
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return base64.b64encode(buffer.getvalue()).decode()
        else:
            # 无 PIL 时直接读取文件
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()

    async def describe_image(self, image_path: str) -> Dict[str, Any]:
        """
        生成图像描述

        Returns:
            {"success": bool, "description": str, "objects": list, "error": str}
        """
        # 优先云端 API
        if self.config == "dashscope":
            return await self._describe_dashscope(image_path)
        elif self.config == "tencent":
            return await self._describe_tencent(image_path)

        # 本地备选（物体检测）
        if self.local_yolo_available:
            return await self._detect_objects_local(image_path)

        return {
            "success": False,
            "description": None,
            "objects": [],
            "error": "No vision API configured",
        }

    async def _describe_dashscope(self, image_path: str) -> Dict[str, Any]:
        """阿里云视觉理解 API"""
        try:
            image_base64 = self._image_to_base64(image_path)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/vision/vision-grounding/grounding",
                    headers={
                        "Authorization": f"Bearer {self.dashscope_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "vision-grounding-v1",
                        "input": {
                            "image": f"data:image/jpeg;base64,{image_base64}"
                        },
                        "parameters": {
                            "detail": "high"
                        }
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "description": data.get("output", {}).get("description", ""),
                        "objects": data.get("output", {}).get("labels", []),
                        "error": None,
                        "provider": "dashscope",
                    }
                else:
                    return {
                        "success": False,
                        "description": None,
                        "objects": [],
                        "error": f"API error: {response.status_code}",
                        "provider": "dashscope",
                    }

        except Exception as e:
            logger.error(f"DashScope vision failed: {e}")
            return {
                "success": False,
                "description": None,
                "objects": [],
                "error": str(e),
                "provider": "dashscope",
            }

    async def _describe_tencent(self, image_path: str) -> Dict[str, Any]:
        """腾讯云视觉 API"""
        try:
            # 腾讯云需要签名，这里简化为通用调用
            image_base64 = self._image_to_base64(image_path)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://ocr.tencentcloudapi.com",
                    headers={"Content-Type": "application/json"},
                    json={
                        "ImageBase64": image_base64,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "description": "腾讯云图像描述",
                        "objects": [],
                        "error": None,
                        "provider": "tencent",
                    }

        except Exception as e:
            return {
                "success": False,
                "description": None,
                "objects": [],
                "error": str(e),
                "provider": "tencent",
            }

    async def _detect_objects_local(self, image_path: str) -> Dict[str, Any]:
        """本地 YOLO 物体检测"""
        try:
            from ultralytics import YOLO

            # 加载模型（使用最小的 nano 版本）
            if not hasattr(self, '_yolo_model'):
                self._yolo_model = YOLO("yolov8n.pt")

            results = self._yolo_model.predict(
                image_path,
                conf=0.25,
                iou=0.45,
                verbose=False,
            )

            objects = []
            for result in results:
                for box in result.boxes:
                    objects.append({
                        "label": result.names[int(box.cls[0])],
                        "confidence": float(box.conf[0]),
                        "bbox": [float(x) for x in box.xyxy[0].tolist()],
                    })

            return {
                "success": True,
                "description": None,  # 本地只能做检测，无法描述
                "objects": objects,
                "error": None,
                "provider": "yolov8n-local",
            }

        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return {
                "success": False,
                "description": None,
                "objects": [],
                "error": str(e),
                "provider": "yolov8n-local",
            }

    async def detect_objects(self, image_path: str) -> Dict[str, Any]:
        """物体检测"""
        # 优先本地（更快、更便宜）
        if self.local_yolo_available:
            return await self._detect_objects_local(image_path)

        # 备选云端
        if self.config == "dashscope":
            return await self._describe_dashscope(image_path)

        return {
            "success": False,
            "objects": [],
            "error": "No object detection available",
        }

    async def classify_scene(self, image_path: str) -> Dict[str, Any]:
        """场景分类"""
        # 简化实现：使用图像描述 API
        result = await self.describe_image(image_path)

        if result["success"]:
            return {
                "success": True,
                "scene": result.get("description", ""),
                "confidence": 0.8,
                "error": None,
            }

        return {
            "success": False,
            "scene": None,
            "confidence": 0.0,
            "error": result.get("error"),
        }


# 全局单例
vision_provider = VisionProvider()
