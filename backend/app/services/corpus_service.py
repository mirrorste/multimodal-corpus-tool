"""语料输出服务"""
import asyncio
import json
import csv
import os
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.models.video import Video
from app.models.frame import Frame
from app.models.subtitle import Subtitle
from app.models.audio_segment import AudioSegment
from app.models.visual_description import VisualDescription
from app.models.multimodal_alignment import MultimodalAlignment
from app.models.metaphor_annotation import MetaphorAnnotation
from app.models.untranslatability_annotation import UntranslatabilityAnnotation
from app.core.config import settings
from app.schemas.corpus import CorpusOutput, VideoInfo, TimelineEntry

logger = logging.getLogger(__name__)


class CorpusService:
    """语料输出服务 - 生成标准化多模态语料"""

    def __init__(self):
        os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.DOWNLOAD_DIR, "corpus"), exist_ok=True)

    async def get_video_corpus(
        self,
        db: AsyncSession,
        video_id: str,
        include_subtitles: bool = True,
        include_audio: bool = True,
        include_visual: bool = True,
        include_annotations: bool = True,
    ) -> Optional[CorpusOutput]:
        """获取单个视频的语料数据"""
        # 获取视频信息
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()

        if not video:
            return None

        # 构建视频信息
        video_info = VideoInfo(
            id=video.id,
            url=video.url,
            title=video.title,
            duration=video.duration,
            resolution=video.resolution,
            platform=video.platform,
        )

        # 获取时间轴数据
        timeline = await self._build_timeline(
            db=db,
            video_id=video_id,
            include_subtitles=include_subtitles,
            include_audio=include_audio,
            include_visual=include_visual,
            include_annotations=include_annotations,
        )

        # 构建元数据
        metadata = await self._build_metadata(db, video_id)

        return CorpusOutput(
            video_info=video_info,
            timeline=timeline,
            metadata=metadata,
        )

    async def _build_timeline(
        self,
        db: AsyncSession,
        video_id: str,
        include_subtitles: bool,
        include_audio: bool,
        include_visual: bool,
        include_annotations: bool,
    ) -> List[TimelineEntry]:
        """构建时间轴"""
        # 获取对齐记录
        alignments_result = await db.execute(
            select(MultimodalAlignment)
            .where(MultimodalAlignment.video_id == video_id)
            .order_by(MultimodalAlignment.timestamp)
        )
        alignments = alignments_result.scalars().all()

        timeline = []

        for alignment in alignments:
            entry = TimelineEntry(
                timestamp=alignment.timestamp,
                subtitle=None,
                audio=None,
                visual=None,
                annotations=None,
            )

            # 添加字幕信息
            if include_subtitles and alignment.subtitle_id:
                subtitle = await self._get_subtitle(db, alignment.subtitle_id)
                if subtitle:
                    entry.subtitle = {
                        "text": subtitle.text,
                        "language": subtitle.language,
                        "source": subtitle.source,
                        "confidence": subtitle.confidence,
                    }

            # 添加音频信息
            if include_audio and alignment.audio_segment_id:
                audio = await self._get_audio_segment(db, alignment.audio_segment_id)
                if audio:
                    entry.audio = {
                        "asr_text": audio.asr_text,
                        "language": audio.language,
                        "confidence": audio.confidence,
                    }

            # 添加视觉信息
            if include_visual and alignment.visual_description_id:
                visual = await self._get_visual_description(db, alignment.visual_description_id)
                if visual:
                    entry.visual = {
                        "description": visual.description,
                        "objects": visual.objects,
                        "scene": visual.scene,
                        "confidence": visual.confidence,
                    }

            # 添加标注信息
            if include_annotations:
                annotations = await self._get_annotations(db, alignment.id)
                if annotations:
                    entry.annotations = annotations

            timeline.append(entry)

        return timeline

    async def _build_metadata(self, db: AsyncSession, video_id: str) -> Dict[str, Any]:
        """构建元数据"""
        # 统计各类数据数量
        frames_count = await self._count_frames(db, video_id)
        subtitles_count = await self._count_subtitles(db, video_id)
        audio_count = await self._count_audio_segments(db, video_id)
        alignments_count = await self._count_alignments(db, video_id)
        metaphors_count = await self._count_metaphors(db, video_id)
        untranslatability_count = await self._count_untranslatability(db, video_id)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "statistics": {
                "frames": frames_count,
                "subtitles": subtitles_count,
                "audio_segments": audio_count,
                "alignments": alignments_count,
                "metaphor_annotations": metaphors_count,
                "untranslatability_annotations": untranslatability_count,
            },
        }

    async def _count_frames(self, db: AsyncSession, video_id: str) -> int:
        result = await db.execute(select(Frame).where(Frame.video_id == video_id))
        return len(result.scalars().all())

    async def _count_subtitles(self, db: AsyncSession, video_id: str) -> int:
        result = await db.execute(select(Subtitle).where(Subtitle.video_id == video_id))
        return len(result.scalars().all())

    async def _count_audio_segments(self, db: AsyncSession, video_id: str) -> int:
        result = await db.execute(select(AudioSegment).where(AudioSegment.video_id == video_id))
        return len(result.scalars().all())

    async def _count_alignments(self, db: AsyncSession, video_id: str) -> int:
        result = await db.execute(select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id))
        return len(result.scalars().all())

    async def _count_metaphors(self, db: AsyncSession, video_id: str) -> int:
        alignments = await self._count_alignments(db, video_id)
        count = 0
        alignments_result = await db.execute(select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id))
        for alignment in alignments_result.scalars().all():
            metaphors_result = await db.execute(
                select(MetaphorAnnotation).where(MetaphorAnnotation.alignment_id == alignment.id)
            )
            count += len(metaphors_result.scalars().all())
        return count

    async def _count_untranslatability(self, db: AsyncSession, video_id: str) -> int:
        count = 0
        alignments_result = await db.execute(select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id))
        for alignment in alignments_result.scalars().all():
            untrans_result = await db.execute(
                select(UntranslatabilityAnnotation).where(UntranslatabilityAnnotation.alignment_id == alignment.id)
            )
            count += len(untrans_result.scalars().all())
        return count

    async def _get_subtitle(self, db: AsyncSession, subtitle_id: str) -> Optional[Subtitle]:
        result = await db.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
        return result.scalar_one_or_none()

    async def _get_audio_segment(self, db: AsyncSession, audio_id: str) -> Optional[AudioSegment]:
        result = await db.execute(select(AudioSegment).where(AudioSegment.id == audio_id))
        return result.scalar_one_or_none()

    async def _get_visual_description(self, db: AsyncSession, visual_id: str) -> Optional[VisualDescription]:
        result = await db.execute(select(VisualDescription).where(VisualDescription.id == visual_id))
        return result.scalar_one_or_none()

    async def _get_annotations(self, db: AsyncSession, alignment_id: str) -> Optional[Dict[str, Any]]:
        # 获取隐喻标注
        metaphors_result = await db.execute(
            select(MetaphorAnnotation).where(MetaphorAnnotation.alignment_id == alignment_id)
        )
        metaphors = metaphors_result.scalars().all()

        # 获取不可译性标注
        untrans_result = await db.execute(
            select(UntranslatabilityAnnotation).where(UntranslatabilityAnnotation.alignment_id == alignment_id)
        )
        untranslatability = untrans_result.scalars().all()

        if not metaphors and not untranslatability:
            return None

        annotations = {
            "metaphors": [],
            "untranslatability": [],
        }

        for m in metaphors:
            annotations["metaphors"].append({
                "id": m.id,
                "type": m.type,
                "source_domain": m.source_domain,
                "target_domain": m.target_domain,
                "trigger": m.trigger,
                "confidence": m.confidence,
            })

        for u in untranslatability:
            annotations["untranslatability"].append({
                "id": u.id,
                "type": u.type,
                "category": u.category,
                "description": u.description,
                "severity": u.severity,
                "confidence": u.confidence,
            })

        return annotations

    async def export_to_json(
        self,
        db: AsyncSession,
        video_id: str,
        output_path: Optional[str] = None,
        include_subtitles: bool = True,
        include_audio: bool = True,
        include_visual: bool = True,
        include_annotations: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """导出为 JSON 格式"""
        result = {
            "success": False,
            "file_path": None,
            "error": None,
        }

        try:
            # 获取语料数据
            corpus = await self.get_video_corpus(
                db=db,
                video_id=video_id,
                include_subtitles=include_subtitles,
                include_audio=include_audio,
                include_visual=include_visual,
                include_annotations=include_annotations,
            )

            if not corpus:
                result["error"] = "视频不存在或没有数据"
                return result

            # 确定输出路径
            if not output_path:
                output_path = os.path.join(
                    settings.DOWNLOAD_DIR,
                    "corpus",
                    f"{video_id}_corpus.json"
                )

            # 写入文件
            await asyncio.to_thread(
                self._write_json_file,
                output_path,
                corpus.model_dump()
            )

            result["success"] = True
            result["file_path"] = output_path
            logger.info(f"JSON 导出完成: {output_path}")

            if progress_callback:
                progress_callback({"percent": 100})

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"JSON 导出失败: {e}")

        return result

    async def export_to_csv(
        self,
        db: AsyncSession,
        video_id: str,
        output_path: Optional[str] = None,
        include_subtitles: bool = True,
        include_audio: bool = True,
        include_visual: bool = True,
        include_annotations: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """导出为 CSV 格式"""
        result = {
            "success": False,
            "file_path": None,
            "error": None,
        }

        try:
            # 获取语料数据
            corpus = await self.get_video_corpus(
                db=db,
                video_id=video_id,
                include_subtitles=include_subtitles,
                include_audio=include_audio,
                include_visual=include_visual,
                include_annotations=include_annotations,
            )

            if not corpus:
                result["error"] = "视频不存在或没有数据"
                return result

            # 确定输出路径
            if not output_path:
                output_path = os.path.join(
                    settings.DOWNLOAD_DIR,
                    "corpus",
                    f"{video_id}_corpus.csv"
                )

            # 构建 CSV 数据
            rows = []
            for entry in corpus.timeline:
                row = {
                    "timestamp": entry.timestamp,
                    "subtitle_text": entry.subtitle.get("text", "") if entry.subtitle else "",
                    "subtitle_language": entry.subtitle.get("language", "") if entry.subtitle else "",
                    "asr_text": entry.audio.get("asr_text", "") if entry.audio else "",
                    "visual_description": entry.visual.get("description", "") if entry.visual else "",
                    "scene": entry.visual.get("scene", "") if entry.visual else "",
                    "metaphor_count": len(entry.annotations.get("metaphors", [])) if entry.annotations else 0,
                    "untranslatability_count": len(entry.annotations.get("untranslatability", [])) if entry.annotations else 0,
                }
                rows.append(row)

            # 写入文件
            await asyncio.to_thread(
                self._write_csv_file,
                output_path,
                rows
            )

            result["success"] = True
            result["file_path"] = output_path
            logger.info(f"CSV 导出完成: {output_path}")

            if progress_callback:
                progress_callback({"percent": 100})

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"CSV 导出失败: {e}")

        return result

    def _write_json_file(self, path: str, data: Dict) -> None:
        """写入 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _write_csv_file(self, path: str, rows: List[Dict]) -> None:
        """写入 CSV 文件"""
        if not rows:
            return

        fieldnames = list(rows[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    async def export_annotations_file(
        self,
        db: AsyncSession,
        video_id: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """导出标注文件"""
        result = {
            "success": False,
            "file_path": None,
            "error": None,
        }

        try:
            # 获取所有标注
            annotations_data = await self._get_all_annotations(db, video_id)

            if not annotations_data:
                result["error"] = "没有标注数据"
                return result

            # 确定输出路径
            if not output_path:
                output_path = os.path.join(
                    settings.DOWNLOAD_DIR,
                    "corpus",
                    f"{video_id}_annotations.json"
                )

            # 写入文件
            await asyncio.to_thread(
                self._write_json_file,
                output_path,
                annotations_data
            )

            result["success"] = True
            result["file_path"] = output_path
            logger.info(f"标注文件导出完成: {output_path}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"标注文件导出失败: {e}")

        return result

    async def _get_all_annotations(self, db: AsyncSession, video_id: str) -> Dict[str, Any]:
        """获取所有标注数据"""
        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        annotations_data = {
            "video_id": video_id,
            "annotations": [],
        }

        for alignment in alignments:
            # 获取隐喻标注
            metaphors_result = await db.execute(
                select(MetaphorAnnotation).where(MetaphorAnnotation.alignment_id == alignment.id)
            )
            metaphors = metaphors_result.scalars().all()

            for m in metaphors:
                annotations_data["annotations"].append({
                    "id": m.id,
                    "timestamp": alignment.timestamp,
                    "type": "metaphor",
                    "subtype": m.type,
                    "source_domain": m.source_domain,
                    "target_domain": m.target_domain,
                    "trigger": m.trigger,
                    "confidence": m.confidence,
                })

            # 获取不可译性标注
            untrans_result = await db.execute(
                select(UntranslatabilityAnnotation).where(UntranslatabilityAnnotation.alignment_id == alignment.id)
            )
            untranslatability = untrans_result.scalars().all()

            for u in untranslatability:
                annotations_data["annotations"].append({
                    "id": u.id,
                    "timestamp": alignment.timestamp,
                    "type": "untranslatability",
                    "subtype": u.type,
                    "category": u.category,
                    "description": u.description,
                    "severity": u.severity,
                    "confidence": u.confidence,
                })

        return annotations_data

    async def batch_export(
        self,
        db: AsyncSession,
        video_ids: List[str],
        format: str = "json",
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """批量导出多个视频的语料"""
        result = {
            "success": False,
            "exported_files": [],
            "failed": [],
            "total": len(video_ids),
            "error": None,
        }

        if not output_dir:
            output_dir = os.path.join(settings.DOWNLOAD_DIR, "corpus")
        os.makedirs(output_dir, exist_ok=True)

        try:
            for i, video_id in enumerate(video_ids):
                try:
                    if format == "json":
                        export_result = await self.export_to_json(
                            db=db,
                            video_id=video_id,
                            output_path=os.path.join(output_dir, f"{video_id}_corpus.json"),
                        )
                    else:
                        export_result = await self.export_to_csv(
                            db=db,
                            video_id=video_id,
                            output_path=os.path.join(output_dir, f"{video_id}_corpus.csv"),
                        )

                    if export_result["success"]:
                        result["exported_files"].append(export_result["file_path"])
                    else:
                        result["failed"].append({
                            "video_id": video_id,
                            "reason": export_result["error"],
                        })

                except Exception as e:
                    result["failed"].append({
                        "video_id": video_id,
                        "reason": str(e),
                    })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(video_ids),
                        "percent": round((i + 1) / len(video_ids) * 100, 2),
                    })

            result["success"] = len(result["exported_files"]) > 0
            logger.info(f"批量导出完成: {len(result['exported_files'])} 个文件")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"批量导出失败: {e}")

        return result

    async def generate_statistics_report(
        self,
        db: AsyncSession,
        video_id: str,
    ) -> Dict[str, Any]:
        """生成语料统计报告"""
        # 获取视频信息
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()

        if not video:
            return {"error": "视频不存在"}

        report = {
            "video_info": {
                "id": video.id,
                "title": video.title,
                "duration": video.duration,
                "platform": video.platform,
            },
            "statistics": await self._build_metadata(db, video_id),
            "language_distribution": await self._get_language_distribution(db, video_id),
            "metaphor_distribution": await self._get_metaphor_distribution(db, video_id),
            "untranslatability_distribution": await self._get_untranslatability_distribution(db, video_id),
            "generated_at": datetime.utcnow().isoformat(),
        }

        return report

    async def _get_language_distribution(self, db: AsyncSession, video_id: str) -> Dict[str, int]:
        """获取语言分布"""
        subtitles_result = await db.execute(select(Subtitle).where(Subtitle.video_id == video_id))
        subtitles = subtitles_result.scalars().all()

        distribution = {}
        for subtitle in subtitles:
            lang = subtitle.language or "unknown"
            distribution[lang] = distribution.get(lang, 0) + 1

        return distribution

    async def _get_metaphor_distribution(self, db: AsyncSession, video_id: str) -> Dict[str, int]:
        """获取隐喻类型分布"""
        alignments_result = await db.execute(select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id))
        alignments = alignments_result.scalars().all()

        distribution = {}
        for alignment in alignments:
            metaphors_result = await db.execute(
                select(MetaphorAnnotation).where(MetaphorAnnotation.alignment_id == alignment.id)
            )
            metaphors = metaphors_result.scalars().all()
            for m in metaphors:
                type_key = m.type or "unknown"
                distribution[type_key] = distribution.get(type_key, 0) + 1

        return distribution

    async def _get_untranslatability_distribution(self, db: AsyncSession, video_id: str) -> Dict[str, int]:
        """获取不可译性类型分布"""
        alignments_result = await db.execute(select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id))
        alignments = alignments_result.scalars().all()

        distribution = {}
        for alignment in alignments:
            untrans_result = await db.execute(
                select(UntranslatabilityAnnotation).where(UntranslatabilityAnnotation.alignment_id == alignment.id)
            )
            untranslatability = untrans_result.scalars().all()
            for u in untranslatability:
                type_key = u.type or "unknown"
                distribution[type_key] = distribution.get(type_key, 0) + 1

        return distribution


# 单例实例
corpus_service = CorpusService()