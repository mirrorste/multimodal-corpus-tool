"""视觉描述服务 - 图像描述、物体检测、场景分类、情感分析"""
import asyncio
import os
import json
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.models.visual_description import VisualDescription
from app.models.frame import Frame
from app.core.config import settings
from app.services.ai.vision_provider import vision_provider
from app.services.ai.llm_provider import llm_provider

logger = logging.getLogger(__name__)


class VisualService:
    """视觉描述服务 - 集成 VisionProvider 和 LLMProvider"""

    def __init__(self):
        self.vision_available = vision_provider.is_available()
        self.llm_available = llm_provider.is_available()
        logger.info(
            f"VisualService 初始化: "
            f"Vision={'可用' if self.vision_available else '不可用'}, "
            f"LLM={'可用' if self.llm_available else '不可用'}"
        )

    def is_available(self) -> Dict[str, bool]:
        """检查各功能可用性"""
        return {
            "vision": self.vision_available,
            "llm": self.llm_available,
        }

    # ============ 数据库操作 ============

    async def get_visual_description(
        self, db: AsyncSession, description_id: str
    ) -> Optional[VisualDescription]:
        """获取单个视觉描述"""
        result = await db.execute(
            select(VisualDescription).where(VisualDescription.id == description_id)
        )
        return result.scalar_one_or_none()

    async def get_visual_descriptions_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        scene: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[VisualDescription]:
        """获取视频的所有视觉描述"""
        # 通过帧关联查询
        query = (
            select(VisualDescription)
            .join(Frame, VisualDescription.frame_id == Frame.id)
            .where(Frame.video_id == video_id)
        )
        if scene:
            query = query.where(VisualDescription.scene == scene)
        query = query.order_by(VisualDescription.created_at.desc())
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_visual_descriptions_by_frame(
        self,
        db: AsyncSession,
        frame_id: str,
    ) -> List[VisualDescription]:
        """获取单帧的所有视觉描述"""
        result = await db.execute(
            select(VisualDescription).where(VisualDescription.frame_id == frame_id)
        )
        return result.scalars().all()

    async def create_visual_description(
        self,
        db: AsyncSession,
        frame_id: str,
        description: Optional[str] = None,
        objects: Optional[list] = None,
        scene: Optional[str] = None,
        emotions: Optional[list] = None,
        confidence: Optional[float] = None,
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
        return visual_desc

    async def update_visual_description(
        self,
        db: AsyncSession,
        description_id: str,
        description: Optional[str] = None,
        objects: Optional[list] = None,
        scene: Optional[str] = None,
        emotions: Optional[list] = None,
        confidence: Optional[float] = None,
    ) -> Optional[VisualDescription]:
        """更新视觉描述（人工校正）"""
        visual_desc = await self.get_visual_description(db, description_id)
        if not visual_desc:
            return None

        if description is not None:
            visual_desc.description = description
        if objects is not None:
            visual_desc.objects = objects
        if scene is not None:
            visual_desc.scene = scene
        if emotions is not None:
            visual_desc.emotions = emotions
        if confidence is not None:
            visual_desc.confidence = confidence

        await db.commit()
        await db.refresh(visual_desc)
        return visual_desc

    # ============ 单帧分析 ============

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
        """分析单帧图像

        Args:
            enable_description: 生成图像描述
            enable_object_detection: 物体检测
            enable_scene_classification: 场景分类
            enable_emotion_detection: 情感分析
        """
        result = {
            "success": False,
            "description_id": None,
            "description": None,
            "objects": None,
            "scene": None,
            "emotions": None,
            "confidence": 0.0,
            "providers": {},
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
            providers = {}

            # 1. 图像描述
            if enable_description:
                if progress_callback:
                    progress_callback({"step": "description", "status": "processing"})
                desc_result = await vision_provider.describe_image(frame.image_path)
                if desc_result.get("success"):
                    analysis_result["description"] = desc_result.get("description")
                    analysis_result["confidence"] = desc_result.get("confidence", 0.85)
                    providers["description"] = desc_result.get("provider", "unknown")
                else:
                    logger.warning(f"图像描述失败: {desc_result.get('error')}")

            # 2. 物体检测
            if enable_object_detection:
                if progress_callback:
                    progress_callback({"step": "objects", "status": "processing"})
                objects_result = await vision_provider.detect_objects(frame.image_path)
                if objects_result.get("success"):
                    analysis_result["objects"] = objects_result.get("objects", [])
                    providers["objects"] = objects_result.get("provider", "unknown")
                else:
                    logger.warning(f"物体检测失败: {objects_result.get('error')}")

            # 3. 场景分类
            if enable_scene_classification:
                if progress_callback:
                    progress_callback({"step": "scene", "status": "processing"})
                scene_result = await self._classify_scene(frame.image_path, analysis_result)
                if scene_result.get("success"):
                    analysis_result["scene"] = scene_result.get("scene")
                    providers["scene"] = scene_result.get("provider", "unknown")

            # 4. 情感分析
            if enable_emotion_detection:
                if progress_callback:
                    progress_callback({"step": "emotions", "status": "processing"})
                emotions_result = await self._detect_emotions(
                    frame.image_path, analysis_result
                )
                if emotions_result.get("success"):
                    analysis_result["emotions"] = emotions_result.get("emotions", [])
                    providers["emotions"] = emotions_result.get("provider", "unknown")

            # 创建视觉描述记录
            visual_desc = await self.create_visual_description(
                db=db,
                frame_id=frame_id,
                description=analysis_result.get("description"),
                objects=analysis_result.get("objects"),
                scene=analysis_result.get("scene"),
                emotions=analysis_result.get("emotions"),
                confidence=analysis_result.get("confidence", 0.0),
            )

            result["success"] = True
            result["description_id"] = visual_desc.id
            result["description"] = analysis_result.get("description")
            result["objects"] = analysis_result.get("objects")
            result["scene"] = analysis_result.get("scene")
            result["emotions"] = analysis_result.get("emotions")
            result["confidence"] = analysis_result.get("confidence", 0.0)
            result["providers"] = providers

            if progress_callback:
                progress_callback({
                    "step": "completed",
                    "status": "done",
                    "description_id": visual_desc.id,
                })

            logger.info(f"帧分析完成: {frame_id}, providers: {providers}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"帧分析失败: {e}")

        return result

    # ============ 批量分析 ============

    async def analyze_video_frames(
        self,
        db: AsyncSession,
        video_id: str,
        frame_ids: Optional[List[str]] = None,
        enable_description: bool = True,
        enable_object_detection: bool = True,
        enable_scene_classification: bool = False,
        enable_emotion_detection: bool = False,
        skip_existing: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """批量分析视频帧

        Args:
            frame_ids: 指定帧ID列表，为空则分析所有帧
            skip_existing: 跳过已有描述的帧
        """
        result = {
            "success": False,
            "descriptions": [],
            "total_frames": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "error": None,
        }

        # 获取要分析的帧
        if frame_ids:
            frames_result = await db.execute(
                select(Frame)
                .where(Frame.id.in_(frame_ids), Frame.video_id == video_id)
                .order_by(Frame.timestamp)
            )
        else:
            frames_result = await db.execute(
                select(Frame)
                .where(Frame.video_id == video_id)
                .order_by(Frame.timestamp)
            )
        frames = frames_result.scalars().all()

        if not frames:
            result["error"] = "没有可用的帧"
            return result

        try:
            frames_to_analyze = []

            for frame in frames:
                if skip_existing:
                    # 检查是否已有描述
                    existing = await self.get_visual_descriptions_by_frame(db, frame.id)
                    if existing:
                        result["skipped_count"] += 1
                        continue
                frames_to_analyze.append(frame)

            result["total_frames"] = len(frames)
            total_to_analyze = len(frames_to_analyze)

            if total_to_analyze == 0:
                result["success"] = True
                return result

            # 批量分析
            for i, frame in enumerate(frames_to_analyze):
                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": total_to_analyze,
                        "percent": round((i + 1) / total_to_analyze * 100, 2),
                        "frame_id": frame.id,
                    })

                frame_result = await self.analyze_frame(
                    db=db,
                    frame_id=frame.id,
                    enable_description=enable_description,
                    enable_object_detection=enable_object_detection,
                    enable_scene_classification=enable_scene_classification,
                    enable_emotion_detection=enable_emotion_detection,
                )

                if frame_result["success"]:
                    result["descriptions"].append({
                        "frame_id": frame.id,
                        "description_id": frame_result.get("description_id"),
                        "description": frame_result.get("description"),
                        "objects": frame_result.get("objects"),
                        "providers": frame_result.get("providers", {}),
                    })
                    result["success_count"] += 1
                else:
                    result["failed_count"] += 1
                    logger.warning(
                        f"帧 {frame.id} 分析失败: {frame_result.get('error')}"
                    )

            result["success"] = True
            logger.info(
                f"视频帧分析完成: 成功 {result['success_count']}, "
                f"失败 {result['failed_count']}, 跳过 {result['skipped_count']}"
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"视频帧分析失败: {e}")

        return result

    # ============ 场景分类与情感分析（使用 LLM） ============

    async def _classify_scene(
        self, image_path: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """场景分类

        策略：
        1. 如果有物体检测结果，使用 LLM 基于物体推断场景
        2. 否则使用 VisionProvider 的图像描述能力
        """
        try:
            objects = context.get("objects", [])
            description = context.get("description", "")

            if self.llm_available and (objects or description):
                # 基于已有信息推断场景
                prompt_parts = ["请根据以下信息判断图片所属的场景类型（仅返回场景名称，如：室内/室外/城市/自然/海滩/餐厅/办公室/教室/街道 等）。\n"]

                if description:
                    prompt_parts.append(f"图像描述：{description}\n")
                if objects:
                    obj_labels = [obj.get("label", "") for obj in objects[:10] if obj.get("label")]
                    if obj_labels:
                        prompt_parts.append(f"检测到的物体：{', '.join(obj_labels)}\n")

                prompt = "".join(prompt_parts)

                llm_result = await llm_provider.chat(
                    messages=[
                        {"role": "system", "content": "你是一个图像场景分类助手。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )

                if llm_result.get("success"):
                    scene = llm_result.get("text", "").strip()
                    # 清理输出（移除可能的多余字符）
                    scene = scene.replace("\n", " ").strip()
                    return {
                        "success": True,
                        "scene": scene,
                        "confidence": 0.8,
                        "provider": llm_result.get("provider", "llm"),
                    }

            # 备选：使用 VisionProvider
            scene_result = await vision_provider.classify_scene(image_path)
            if scene_result.get("success"):
                return {
                    "success": True,
                    "scene": scene_result.get("scene"),
                    "confidence": scene_result.get("confidence", 0.7),
                    "provider": "vision_provider",
                }

            return {
                "success": False,
                "error": "场景分类失败",
            }

        except Exception as e:
            logger.warning(f"场景分类失败: {e}")
            return {"success": False, "error": str(e)}

    async def _detect_emotions(
        self, image_path: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """情感分析

        使用 LLM 基于图像描述和物体检测结果推断情感
        """
        try:
            description = context.get("description", "")
            objects = context.get("objects", [])

            if not self.llm_available:
                return {"success": False, "error": "LLM 服务不可用"}

            if not description and not objects:
                return {"success": False, "error": "缺少图像描述信息"}

            # 构建 prompt
            prompt_parts = [
                "请根据以下信息分析图片传达的情感（返回 JSON 格式："
                '[{"label": "情感标签", "confidence": 0.0-1.0}]）。\n'
                "情感标签可选：happy, sad, angry, surprised, fearful, disgusted, neutral, calm, tense, warm, cold 等。\n"
            ]

            if description:
                prompt_parts.append(f"图像描述：{description}\n")
            if objects:
                obj_labels = [obj.get("label", "") for obj in objects[:10] if obj.get("label")]
                if obj_labels:
                    prompt_parts.append(f"检测到的物体：{', '.join(obj_labels)}\n")

            prompt = "".join(prompt_parts)

            llm_result = await llm_provider.chat(
                messages=[
                    {"role": "system", "content": "你是一个图像情感分析助手，只返回 JSON 格式结果。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

            if llm_result.get("success"):
                text = llm_result.get("text", "").strip()
                emotions = self._parse_emotions_json(text)
                if emotions:
                    return {
                        "success": True,
                        "emotions": emotions,
                        "provider": llm_result.get("provider", "llm"),
                    }

            return {"success": False, "error": "情感分析失败"}

        except Exception as e:
            logger.warning(f"情感分析失败: {e}")
            return {"success": False, "error": str(e)}

    def _parse_emotions_json(self, text: str) -> List[Dict[str, Any]]:
        """解析情感分析返回的 JSON"""
        try:
            # 尝试直接解析
            emotions = json.loads(text)
            if isinstance(emotions, list):
                return emotions

            # 尝试提取 JSON 代码块
            import re
            match = re.search(r"\[[\s\S]*?\]", text)
            if match:
                emotions = json.loads(match.group(0))
                if isinstance(emotions, list):
                    return emotions

            # 兜底：返回简单结果
            return [{"label": text[:50], "confidence": 0.5}]

        except Exception:
            return [{"label": text[:50] if text else "unknown", "confidence": 0.5}]

    # ============ 删除 ============

    async def delete_visual_descriptions_by_video(
        self, db: AsyncSession, video_id: str
    ) -> int:
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
