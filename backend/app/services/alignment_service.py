"""多模态对齐服务"""
import asyncio
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.models.multimodal_alignment import MultimodalAlignment
from app.models.video import Video
from app.models.frame import Frame
from app.models.subtitle import Subtitle
from app.models.audio_segment import AudioSegment
from app.models.visual_description import VisualDescription
from app.core.config import settings

logger = logging.getLogger(__name__)


class AlignmentService:
    """多模态对齐服务 - 将字幕、音频、画面进行时间轴和语义对齐"""

    def __init__(self):
        self.semantic_threshold = 0.7
        self.time_tolerance = 0.5  # 时间容差（秒）
        logger.info("多模态对齐服务初始化完成")

    async def get_alignment(self, db: AsyncSession, alignment_id: str) -> Optional[MultimodalAlignment]:
        """获取单条对齐记录"""
        result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.id == alignment_id)
        )
        return result.scalar_one_or_none()

    async def get_alignments_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[MultimodalAlignment]:
        """获取视频的所有对齐记录"""
        query = select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        if start_time is not None:
            query = query.where(MultimodalAlignment.timestamp >= start_time)
        if end_time is not None:
            query = query.where(MultimodalAlignment.timestamp <= end_time)
        query = query.order_by(MultimodalAlignment.timestamp)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_alignment(
        self,
        db: AsyncSession,
        video_id: str,
        timestamp: float,
        subtitle_id: Optional[str] = None,
        audio_segment_id: Optional[str] = None,
        frame_id: Optional[str] = None,
        visual_description_id: Optional[str] = None,
        alignment_score: Optional[float] = None,
    ) -> MultimodalAlignment:
        """创建对齐记录"""
        alignment = MultimodalAlignment(
            video_id=video_id,
            timestamp=timestamp,
            subtitle_id=subtitle_id,
            audio_segment_id=audio_segment_id,
            frame_id=frame_id,
            visual_description_id=visual_description_id,
            alignment_score=alignment_score,
        )
        db.add(alignment)
        await db.commit()
        await db.refresh(alignment)
        return alignment

    async def batch_create_alignments(
        self,
        db: AsyncSession,
        alignments_data: List[Dict[str, Any]],
    ) -> List[MultimodalAlignment]:
        """批量创建对齐记录"""
        alignments = []
        for data in alignments_data:
            alignment = MultimodalAlignment(
                video_id=data["video_id"],
                timestamp=data["timestamp"],
                subtitle_id=data.get("subtitle_id"),
                audio_segment_id=data.get("audio_segment_id"),
                frame_id=data.get("frame_id"),
                visual_description_id=data.get("visual_description_id"),
                alignment_score=data.get("alignment_score", 0.5),
            )
            db.add(alignment)
            alignments.append(alignment)
        await db.commit()
        for alignment in alignments:
            await db.refresh(alignment)
        return alignments

    async def perform_time_alignment(
        self,
        db: AsyncSession,
        video_id: str,
        time_tolerance: Optional[float] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行时间轴对齐"""
        result = {
            "success": False,
            "alignments": [],
            "total_alignments": 0,
            "error": None,
        }

        tolerance = time_tolerance or self.time_tolerance

        # 获取所有多模态数据
        frames = await self._get_frames(db, video_id)
        subtitles = await self._get_subtitles(db, video_id)
        audio_segments = await self._get_audio_segments(db, video_id)
        visual_descriptions = await self._get_visual_descriptions(db, video_id)

        if not frames and not subtitles and not audio_segments:
            result["error"] = "没有可用的多模态数据"
            return result

        try:
            # 按时间戳聚合数据
            alignments_data = await self._align_by_time(
                video_id=video_id,
                frames=frames,
                subtitles=subtitles,
                audio_segments=audio_segments,
                visual_descriptions=visual_descriptions,
                tolerance=tolerance,
            )

            # 批量创建对齐记录
            alignments = await self.batch_create_alignments(db, alignments_data)

            result["success"] = True
            result["alignments"] = [a.id for a in alignments]
            result["total_alignments"] = len(alignments)
            logger.info(f"时间轴对齐完成: {len(alignments)} 条记录")

            if progress_callback:
                progress_callback({
                    "total": len(alignments),
                    "percent": 100.0,
                })

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"时间轴对齐失败: {e}")

        return result

    async def perform_semantic_alignment(
        self,
        db: AsyncSession,
        video_id: str,
        semantic_threshold: Optional[float] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行语义对齐"""
        result = {
            "success": False,
            "alignments_updated": 0,
            "error": None,
        }

        threshold = semantic_threshold or self.semantic_threshold

        # 先执行时间轴对齐
        time_result = await self.perform_time_alignment(db, video_id)

        if not time_result["success"]:
            result["error"] = time_result["error"]
            return result

        # 获取对齐记录
        alignments = await self.get_alignments_by_video(db, video_id)

        try:
            updated_count = 0

            for i, alignment in enumerate(alignments):
                # 计算语义相似度
                semantic_score = await self._calculate_semantic_similarity(db, alignment)

                # 更新对齐分数
                if semantic_score > threshold:
                    alignment.alignment_score = semantic_score
                    updated_count += 1

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            await db.commit()

            result["success"] = True
            result["alignments_updated"] = updated_count
            logger.info(f"语义对齐完成: {updated_count} 条更新")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"语义对齐失败: {e}")

        return result

    async def _get_frames(self, db: AsyncSession, video_id: str) -> List[Frame]:
        """获取视频帧列表"""
        result = await db.execute(
            select(Frame).where(Frame.video_id == video_id).order_by(Frame.timestamp)
        )
        return result.scalars().all()

    async def _get_subtitles(self, db: AsyncSession, video_id: str) -> List[Subtitle]:
        """获取字幕列表"""
        result = await db.execute(
            select(Subtitle).where(Subtitle.video_id == video_id).order_by(Subtitle.start_time)
        )
        return result.scalars().all()

    async def _get_audio_segments(self, db: AsyncSession, video_id: str) -> List[AudioSegment]:
        """获取音频片段列表"""
        result = await db.execute(
            select(AudioSegment).where(AudioSegment.video_id == video_id).order_by(AudioSegment.start_time)
        )
        return result.scalars().all()

    async def _get_visual_descriptions(self, db: AsyncSession, video_id: str) -> List[VisualDescription]:
        """获取视觉描述列表"""
        # 通过帧关联获取
        frames = await self._get_frames(db, video_id)
        descriptions = []
        for frame in frames:
            desc_result = await db.execute(
                select(VisualDescription).where(VisualDescription.frame_id == frame.id)
            )
            desc = desc_result.scalar_one_or_none()
            if desc:
                descriptions.append({"frame": frame, "description": desc})
        return descriptions

    async def _align_by_time(
        self,
        video_id: str,
        frames: List[Frame],
        subtitles: List[Subtitle],
        audio_segments: List[AudioSegment],
        visual_descriptions: List[Dict],
        tolerance: float,
    ) -> List[Dict[str, Any]]:
        """按时间戳聚合多模态数据"""
        # 收集所有时间点
        time_points = set()

        for frame in frames:
            time_points.add(frame.timestamp)

        for subtitle in subtitles:
            time_points.add(subtitle.start_time)
            time_points.add(subtitle.end_time)

        for segment in audio_segments:
            time_points.add(segment.start_time)
            time_points.add(segment.end_time)

        # 按时间点创建对齐记录
        alignments_data = []

        for timestamp in sorted(time_points):
            alignment_entry = {
                "video_id": video_id,
                "timestamp": timestamp,
                "subtitle_id": None,
                "audio_segment_id": None,
                "frame_id": None,
                "visual_description_id": None,
                "alignment_score": 0.5,
            }

            # 找到最接近的帧
            closest_frame = self._find_closest_item(frames, timestamp, tolerance, lambda x: x.timestamp)
            if closest_frame:
                alignment_entry["frame_id"] = closest_frame.id

            # 找到覆盖该时间点的字幕
            covering_subtitle = self._find_covering_item(
                subtitles, timestamp, tolerance,
                lambda x: x.start_time, lambda x: x.end_time
            )
            if covering_subtitle:
                alignment_entry["subtitle_id"] = covering_subtitle.id

            # 找到覆盖该时间点的音频片段
            covering_audio = self._find_covering_item(
                audio_segments, timestamp, tolerance,
                lambda x: x.start_time, lambda x: x.end_time
            )
            if covering_audio:
                alignment_entry["audio_segment_id"] = covering_audio.id

            # 找到对应的视觉描述
            for item in visual_descriptions:
                frame = item["frame"]
                if abs(frame.timestamp - timestamp) <= tolerance:
                    alignment_entry["visual_description_id"] = item["description"].id
                    break

            # 计算对齐分数（有多少模态被对齐）
            aligned_count = sum([
                alignment_entry["subtitle_id"] is not None,
                alignment_entry["audio_segment_id"] is not None,
                alignment_entry["frame_id"] is not None,
                alignment_entry["visual_description_id"] is not None,
            ])
            alignment_entry["alignment_score"] = aligned_count / 4.0

            alignments_data.append(alignment_entry)

        return alignments_data

    def _find_closest_item(
        self,
        items: List[Any],
        timestamp: float,
        tolerance: float,
        get_time: Callable,
    ) -> Optional[Any]:
        """找到最接近指定时间戳的项"""
        closest = None
        min_diff = float("inf")

        for item in items:
            diff = abs(get_time(item) - timestamp)
            if diff <= tolerance and diff < min_diff:
                closest = item
                min_diff = diff

        return closest

    def _find_covering_item(
        self,
        items: List[Any],
        timestamp: float,
        tolerance: float,
        get_start: Callable,
        get_end: Callable,
    ) -> Optional[Any]:
        """找到覆盖指定时间戳的项"""
        for item in items:
            start = get_start(item)
            end = get_end(item)
            if start - tolerance <= timestamp <= end + tolerance:
                return item
        return None

    async def _calculate_semantic_similarity(
        self,
        db: AsyncSession,
        alignment: MultimodalAlignment,
    ) -> float:
        """计算语义相似度"""
        texts = []

        # 获取字幕文本
        if alignment.subtitle_id:
            subtitle = await self._get_subtitle(db, alignment.subtitle_id)
            if subtitle and subtitle.text:
                texts.append(subtitle.text)

        # 获取 ASR 文本
        if alignment.audio_segment_id:
            audio = await self._get_audio_segment(db, alignment.audio_segment_id)
            if audio and audio.asr_text:
                texts.append(audio.asr_text)

        # 获取视觉描述
        if alignment.visual_description_id:
            visual = await self._get_visual_description(db, alignment.visual_description_id)
            if visual and visual.description:
                texts.append(visual.description)

        if len(texts) < 2:
            return 0.5  # 只有一种模态时返回中等分数

        # 计算文本相似度（简化实现）
        try:
            similarity = await self._text_similarity(texts[0], texts[1])
            return similarity
        except Exception:
            return 0.5

    async def _text_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的语义相似度"""
        # 简化实现：使用词汇重叠率
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    async def _get_subtitle(self, db: AsyncSession, subtitle_id: str) -> Optional[Subtitle]:
        """获取字幕"""
        result = await db.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
        return result.scalar_one_or_none()

    async def _get_audio_segment(self, db: AsyncSession, audio_id: str) -> Optional[AudioSegment]:
        """获取音频片段"""
        result = await db.execute(select(AudioSegment).where(AudioSegment.id == audio_id))
        return result.scalar_one_or_none()

    async def _get_visual_description(self, db: AsyncSession, visual_id: str) -> Optional[VisualDescription]:
        """获取视觉描述"""
        result = await db.execute(select(VisualDescription).where(VisualDescription.id == visual_id))
        return result.scalar_one_or_none()

    async def get_aligned_timeline(
        self,
        db: AsyncSession,
        video_id: str,
    ) -> List[Dict[str, Any]]:
        """获取对齐后的时间轴数据"""
        alignments = await self.get_alignments_by_video(db, video_id)

        timeline = []
        for alignment in alignments:
            entry = {
                "timestamp": alignment.timestamp,
                "alignment_id": alignment.id,
                "alignment_score": alignment.alignment_score,
            }

            # 加载字幕信息
            if alignment.subtitle_id:
                subtitle = await self._get_subtitle(db, alignment.subtitle_id)
                if subtitle:
                    entry["subtitle"] = {
                        "text": subtitle.text,
                        "language": subtitle.language,
                        "source": subtitle.source,
                    }

            # 加载音频信息
            if alignment.audio_segment_id:
                audio = await self._get_audio_segment(db, alignment.audio_segment_id)
                if audio:
                    entry["audio"] = {
                        "asr_text": audio.asr_text,
                        "language": audio.language,
                    }

            # 加载视觉信息
            if alignment.visual_description_id:
                visual = await self._get_visual_description(db, alignment.visual_description_id)
                if visual:
                    entry["visual"] = {
                        "description": visual.description,
                        "objects": visual.objects,
                        "scene": visual.scene,
                    }

            timeline.append(entry)

        return timeline

    async def delete_alignments_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有对齐记录"""
        alignments = await self.get_alignments_by_video(db, video_id)
        count = 0
        for alignment in alignments:
            await db.delete(alignment)
            count += 1
        await db.commit()
        return count


# 单例实例
alignment_service = AlignmentService()