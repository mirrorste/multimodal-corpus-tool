"""字幕提取服务"""
import asyncio
import os
import re
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.models.subtitle import Subtitle
from app.models.video import Video
from app.models.frame import Frame
from app.core.config import settings

logger = logging.getLogger(__name__)


class SubtitleService:
    """字幕提取服务 - 从视频提取字幕（内嵌字幕和OCR）"""

    def __init__(self):
        self.ocr_available = self._check_ocr_available()
        logger.info(f"OCR 可用: {self.ocr_available}")

    def _check_ocr_available(self) -> bool:
        """检查 OCR 库是否可用"""
        try:
            # 检查 paddleocr 是否安装
            import paddleocr
            return True
        except ImportError:
            logger.warning("PaddleOCR 未安装，OCR 功能不可用")
            return False

    async def get_subtitle(self, db: AsyncSession, subtitle_id: str) -> Optional[Subtitle]:
        """获取单条字幕"""
        result = await db.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
        return result.scalar_one_or_none()

    async def get_subtitles_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        language: Optional[str] = None,
    ) -> List[Subtitle]:
        """获取视频的所有字幕"""
        query = select(Subtitle).where(Subtitle.video_id == video_id)
        if start_time is not None:
            query = query.where(Subtitle.start_time >= start_time)
        if end_time is not None:
            query = query.where(Subtitle.end_time <= end_time)
        if language is not None:
            query = query.where(Subtitle.language == language)
        query = query.order_by(Subtitle.start_time)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_subtitle(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: float,
        end_time: float,
        text: str,
        language: Optional[str] = None,
        source: str = "OCR",
        frame_id: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Subtitle:
        """创建字幕记录"""
        subtitle = Subtitle(
            video_id=video_id,
            start_time=start_time,
            end_time=end_time,
            text=text,
            language=language,
            source=source,
            frame_id=frame_id,
            confidence=confidence,
        )
        db.add(subtitle)
        await db.commit()
        await db.refresh(subtitle)
        return subtitle

    async def batch_create_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        subtitles_data: List[Dict[str, Any]],
    ) -> List[Subtitle]:
        """批量创建字幕记录"""
        subtitles = []
        for data in subtitles_data:
            subtitle = Subtitle(
                video_id=video_id,
                start_time=data["start_time"],
                end_time=data["end_time"],
                text=data.get("text"),
                language=data.get("language"),
                source=data.get("source", "OCR"),
                frame_id=data.get("frame_id"),
                confidence=data.get("confidence"),
            )
            db.add(subtitle)
            subtitles.append(subtitle)
        await db.commit()
        for subtitle in subtitles:
            await db.refresh(subtitle)
        return subtitles

    async def extract_embedded_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """提取内嵌字幕轨道"""
        result = {
            "success": False,
            "subtitles": [],
            "total_subtitles": 0,
            "error": None,
        }

        # 获取视频信息
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()

        if not video:
            result["error"] = "视频不存在"
            return result

        if not video.file_path or not os.path.exists(video.file_path):
            result["error"] = "视频文件不存在"
            return result

        try:
            # 使用 ffmpeg 提取内嵌字幕
            subtitle_output = os.path.join(
                settings.DOWNLOAD_DIR,
                "subtitles",
                f"{video_id}_embedded.srt"
            )
            os.makedirs(os.path.dirname(subtitle_output), exist_ok=True)

            # 先检查视频是否有字幕轨道
            track_info = await self._get_subtitle_tracks(video.file_path)

            if not track_info:
                logger.info("视频没有内嵌字幕轨道")
                result["error"] = "视频没有内嵌字幕轨道"
                return result

            # 提取字幕
            cmd = [
                "ffmpeg",
                "-i", video.file_path,
                "-map", "0:s:0",  # 选择第一个字幕轨道
                "-y",
                subtitle_output,
            ]

            await asyncio.to_thread(self._run_ffmpeg, cmd)

            # 解析 SRT 文件
            subtitles_data = await self._parse_srt_file(subtitle_output)

            # 批量创建字幕记录
            subtitles = await self.batch_create_subtitles(
                db=db,
                video_id=video_id,
                subtitles_data=[{
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "text": s["text"],
                    "language": language or track_info.get("language", "unknown"),
                    "source": "embedded",
                    "confidence": 1.0,
                } for s in subtitles_data],
            )

            result["success"] = True
            result["subtitles"] = [s.id for s in subtitles]
            result["total_subtitles"] = len(subtitles)
            logger.info(f"内嵌字幕提取完成: {len(subtitles)} 条")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"内嵌字幕提取失败: {e}")

        return result

    async def _get_subtitle_tracks(self, video_path: str) -> Optional[Dict[str, Any]]:
        """获取视频的字幕轨道信息"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_streams",
            "-select_streams", "s",
            "-of", "json",
            video_path,
        ]
        try:
            process = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )
            import json
            data = json.loads(process.stdout)
            streams = data.get("streams", [])
            if streams:
                return {
                    "index": streams[0].get("index"),
                    "language": streams[0].get("tags", {}).get("language", "unknown"),
                    "codec": streams[0].get("codec_name"),
                }
            return None
        except Exception:
            return None

    async def _parse_srt_file(self, srt_path: str) -> List[Dict[str, Any]]:
        """解析 SRT 字幕文件"""
        subtitles = []
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # SRT 格式解析
            pattern = r"(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s+(.*?)(?=\n\n|\n$)"
            matches = re.findall(pattern, content, re.DOTALL)

            for match in matches:
                index = int(match[0])
                start_time = self._srt_time_to_seconds(match[1])
                end_time = self._srt_time_to_seconds(match[2])
                text = match[3].strip().replace("\n", " ")

                subtitles.append({
                    "index": index,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": text,
                })

        except Exception as e:
            logger.error(f"解析 SRT 文件失败: {e}")

        return subtitles

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """将 SRT 时间格式转换为秒"""
        hours, minutes, seconds_ms = time_str.split(":")
        seconds, milliseconds = seconds_ms.split(",")
        return (
            int(hours) * 3600 +
            int(minutes) * 60 +
            int(seconds) +
            int(milliseconds) / 1000
        )

    async def extract_ocr_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """使用 OCR 从帧中提取硬字幕"""
        result = {
            "success": False,
            "subtitles": [],
            "total_subtitles": 0,
            "error": None,
        }

        # 获取有字幕的帧
        frames_result = await db.execute(
            select(Frame).where(Frame.video_id == video_id).order_by(Frame.timestamp)
        )
        frames = frames_result.scalars().all()

        if not frames:
            result["error"] = "没有可用的帧"
            return result

        try:
            subtitles_data = []

            # 初始化 OCR（如果可用）
            ocr_engine = None
            if self.ocr_available:
                import paddleocr
                ocr_engine = paddleocr.PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",  # 支持中英文
                    show_log=False,
                )

            # 对每帧进行 OCR
            for i, frame in enumerate(frames):
                if frame.image_path and os.path.exists(frame.image_path):
                    ocr_result = await self._ocr_frame(frame.image_path, ocr_engine)

                    if ocr_result and ocr_result.get("text"):
                        subtitles_data.append({
                            "start_time": frame.timestamp,
                            "end_time": frame.timestamp + 2,  # 默认2秒时长
                            "text": ocr_result["text"],
                            "language": ocr_result.get("language", "unknown"),
                            "source": "OCR",
                            "frame_id": frame.id,
                            "confidence": ocr_result.get("confidence", 0.5),
                        })

                    if progress_callback:
                        progress_callback({
                            "current": i + 1,
                            "total": len(frames),
                            "percent": round((i + 1) / len(frames) * 100, 2),
                        })

            # 去重和合并相邻字幕
            subtitles_data = self._merge_adjacent_subtitles(subtitles_data)

            # 批量创建字幕记录
            subtitles = await self.batch_create_subtitles(db, video_id, subtitles_data)

            result["success"] = True
            result["subtitles"] = [s.id for s in subtitles]
            result["total_subtitles"] = len(subtitles)
            logger.info(f"OCR 字幕提取完成: {len(subtitles)} 条")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"OCR 字幕提取失败: {e}")

        return result

    async def _ocr_frame(
        self,
        frame_path: str,
        ocr_engine: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """对单帧进行 OCR"""
        if not ocr_engine:
            # 返回占位结果
            return {
                "text": "",
                "confidence": 0.0,
                "language": "unknown",
            }

        try:
            result = ocr_engine.ocr(frame_path, cls=True)

            if not result or not result[0]:
                return None

            # 合并所有识别到的文本
            texts = []
            confidences = []
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                texts.append(text)
                confidences.append(confidence)

            return {
                "text": " ".join(texts),
                "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
                "language": "zh",  # PaddleOCR 默认中文
            }

        except Exception as e:
            logger.warning(f"OCR 处理失败: {e}")
            return None

    def _merge_adjacent_subtitles(
        self,
        subtitles_data: List[Dict[str, Any]],
        threshold: float = 1.0,  # 时间差阈值
    ) -> List[Dict[str, Any]]:
        """合并相邻的相同字幕"""
        if not subtitles_data:
            return []

        merged = []
        current = subtitles_data[0]

        for i in range(1, len(subtitles_data)):
            next_sub = subtitles_data[i]

            # 如果文本相同且时间相邻
            if (
                next_sub["text"] == current["text"] and
                next_sub["start_time"] - current["end_time"] <= threshold
            ):
                current["end_time"] = next_sub["end_time"]
                current["confidence"] = max(current["confidence"], next_sub["confidence"])
            else:
                merged.append(current)
                current = next_sub

        merged.append(current)
        return merged

    def _run_ffmpeg(self, cmd: List[str]) -> None:
        """运行 ffmpeg 命令"""
        import subprocess
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg 错误: {process.stderr}")

    async def delete_subtitles_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有字幕记录"""
        subtitles = await self.get_subtitles_by_video(db, video_id)
        count = 0
        for subtitle in subtitles:
            await db.delete(subtitle)
            count += 1
        await db.commit()
        return count


# 单例实例
subtitle_service = SubtitleService()