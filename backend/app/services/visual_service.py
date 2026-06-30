"""视觉描述服务 - 低 GPU 依赖版本"""
import asyncio
import os
from typing import Optional, Callable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.visual_description import VisualDescription
from app.models.frame import Frame
from app.core.config import settings

logger = logging.getLogger(__name__)


class VisualService:
    """视觉描述服务 - 使用 AI 提供方（云端 API + 本地轻量检测）"""

    def __init__(self):
        # 延迟导入，避免循环依赖
        self._vision_provider = None
        self._ocr_provider = None

    @property
    def vision_provider(self):
        """懒加载视觉提供方"""
        if self._vision_provider is None:
            from app.services.ai.vision_provider import vision_provider
            self._vision_provider = vision_provider
        return self._vision_provider

    @property
    def ocr_provider(self):
        """懒加载 OCR 提供方"""
        if self._ocr_provider is None:
            from app.services.ai.ocr_provider import ocr_provider
            self._ocr_provider = ocr_provider
        return self._ocr_provider

    def is_available(self) -> Dict[str, bool]:
        """检查各功能可用性"""
        return {
            "vision": self.vision_provider.is_available(),
            "ocr": self.ocr_provider.is_available(),
        }

    async def get_visual_description(self, db: AsyncSession, description_id: str) -> Optional[VisualDescription]:
        """获取单个视觉描述"""
        result = await db.execute(select(VisualDescription).where(VisualDescription.id == description_id))
        return result.scalar_one_or_none()

    async def get_visual_descriptions_by_video(
        self,
        db: AsyncSession,
        video_id: str,
    ) -> list[VisualDescription]:
        """获取视频的所有视觉描述"""
        frames_result = await db.execute(select(Frame).where(Frame.video_id == video_id))
        frames = frames_result.scalars().all()

        descriptions = []
        for frame in frames:
            desc_result = await db.execute(
                select(VisualDescription).where(VisualDescription.frame_id == frame.id)
            )
            desc = desc_result.scalar_one_or_none()
            if desc:
                descriptions.append(desc)
        return descriptions

    async def create_visual_description(
        self,
        db: AsyncSession,
        frame_id: str,
        description: Optional[str] = None,
        objects: Optional[list] = None,
        scene: Optional[str] = None,
        emotions: Optional[list] = None,
        confidence: Optional[float] = None,
        provider: str = "unknown",
    ) -> VisualDescription:
        """创建视觉描述记录"""
        visual_desc = VisualDescription(
            frame_id=frame_id,
            description=description,
            objects=objects,
            scene=scene,
            emotions=emotions,
            confidence=confidence,
        )
        db.add(visual_desc)
        await db.commit()
        await db.refresh(visual_desc)
        logger.info(f"创建视觉描述: {visual_desc.id} (provider: {provider})")
        return visual_desc

    async def analyze_frame(
        self,
        db: AsyncSession,
        frame_id: str,
        enable_description: bool = True,
        enable_object_detection: bool = True,
        enable_scene_classification: bool = False,
        enable_emotion_detection: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """分析单帧图像"""
        result = {
            "success": False,
            "description": None,
            "objects": None,
            "scene": None,
            "emotions": None,
            "confidence": 0.0,
            "provider": "none",
            "error": None,
        }

        # 获取帧信息
        frame_result = await db.execute(select(Frame).where(Frame.id == frame_id))
        frame = frame_result.scalar_one_or_none()

        if not frame:
            result["error"] = "帧不存在"
            return result

        if not frame.image_path or not os.path.exists(frame.image_path):
            result["error"] = "帧图像文件不存在"
            return result

        try:
            analysis_result = {}

            # 图像描述生成（云端 API）
            if enable_description:
                if progress_callback:
                    progress_callback({"step": "description", "status": "processing"})
                desc_result = await self.vision_provider.describe_image(frame.image_path)
                if desc_result.get("success"):
                    analysis_result["description"] = desc_result.get("description")
                    analysis_result["confidence"] = desc_result.get("confidence", 0.85)
                    analysis_result["provider"] = desc_result.get("provider", "cloud")

            # 物体检测（本地 YOLO 或云端）
            if enable_object_detection:
                if progress_callback:
                    progress_callback({"step": "objects", "status": "processing"})
                objects_result = await self.vision_provider.detect_objects(frame.image_path)
                if objects_result.get("success"):
                    analysis_result["objects"] = objects_result.get("objects", [])
                    analysis_result["objects_provider"] = objects_result.get("provider", "cloud")

            # 创建视觉描述记录
            visual_desc = await self.create_visual_description(
                db=db,
                frame_id=frame_id,
                description=analysis_result.get("description"),
                objects=analysis_result.get("objects"),
                scene=analysis_result.get("scene"),
                emotions=analysis_result.get("emotions"),
                confidence=analysis_result.get("confidence", 0.0),
                provider=analysis_result.get("provider", "unknown"),
            )

            result["success"] = True
            result["description_id"] = visual_desc.id
            result["description"] = analysis_result.get("description")
            result["objects"] = analysis_result.get("objects")
            result["scene"] = analysis_result.get("scene")
            result["emotions"] = analysis_result.get("emotions")
            result["confidence"] = analysis_result.get("confidence", 0.0)
            result["provider"] = analysis_result.get("provider", "mixed")

            logger.info(f"帧分析完成: {frame_id}, provider: {result['provider']}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"帧分析失败: {e}")

        return result

    async def analyze_video_frames(
        self,
        db: AsyncSession,
        video_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """分析视频的所有帧"""
        result = {
            "success": False,
            "descriptions": [],
            "total_frames": 0,
            "failed_frames": [],
            "provider": "mixed",
            "error": None,
        }

        # 获取视频的所有帧
        frames_result = await db.execute(
            select(Frame).where(Frame.video_id == video_id).order_by(Frame.timestamp)
        )
        frames = frames_result.scalars().all()

        if not frames:
            result["error"] = "没有可用的帧"
            return result

        try:
            for i, frame in enumerate(frames):
                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(frames),
                        "percent": round((i + 1) / len(frames) * 100, 2),
                        "frame_id": frame.id,
                    })

                frame_result = await self.analyze_frame(db, frame.id)

                if frame_result["success"]:
                    result["descriptions"].append({
                        "frame_id": frame.id,
                        "description_id": frame_result.get("description_id"),
                        "provider": frame_result.get("provider", "unknown"),
                    })
                else:
                    result["failed_frames"].append({
                        "frame_id": frame.id,
                        "error": frame_result.get("error"),
                    })

            result["success"] = True
            result["total_frames"] = len(frames)
            logger.info(f"视频帧分析完成: {len(result['descriptions'])}/{len(frames)}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"视频帧分析失败: {e}")

        return result

    async def delete_visual_descriptions_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有视觉描述记录"""
        descriptions = await self.get_visual_descriptions_by_video(db, video_id)
        count = 0
        for desc in descriptions:
            await db.delete(desc)
            count += 1
        await db.commit()
        return count


# 单例实例
visual_service = VisualService()
