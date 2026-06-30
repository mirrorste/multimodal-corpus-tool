"""音频提取服务"""
import asyncio
import os
import subprocess
from typing import Optional, Callable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.models.audio_segment import AudioSegment
from app.models.video import Video
from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioService:
    """音频提取服务 - 从视频提取音频并进行ASR"""

    def __init__(self):
        self.asr_available = self._check_asr_available()
        logger.info(f"ASR 可用: {self.asr_available}")

    def _check_asr_available(self) -> bool:
        """检查 ASR 库是否可用"""
        try:
            import whisper
            return True
        except ImportError:
            logger.warning("Whisper 未安装，ASR 功能不可用")
            return False

    async def get_audio_segment(self, db: AsyncSession, segment_id: str) -> Optional[AudioSegment]:
        """获取单个音频片段"""
        result = await db.execute(select(AudioSegment).where(AudioSegment.id == segment_id))
        return result.scalar_one_or_none()

    async def get_audio_segments_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[AudioSegment]:
        """获取视频的所有音频片段"""
        query = select(AudioSegment).where(AudioSegment.video_id == video_id)
        if start_time is not None:
            query = query.where(AudioSegment.start_time >= start_time)
        if end_time is not None:
            query = query.where(AudioSegment.end_time <= end_time)
        query = query.order_by(AudioSegment.start_time)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_audio_segment(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: float,
        end_time: float,
        audio_path: Optional[str] = None,
        asr_text: Optional[str] = None,
        language: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> AudioSegment:
        """创建音频片段记录"""
        segment = AudioSegment(
            video_id=video_id,
            start_time=start_time,
            end_time=end_time,
            audio_path=audio_path,
            asr_text=asr_text,
            language=language,
            confidence=confidence,
        )
        db.add(segment)
        await db.commit()
        await db.refresh(segment)
        return segment

    async def batch_create_audio_segments(
        self,
        db: AsyncSession,
        video_id: str,
        segments_data: list[Dict[str, Any]],
    ) -> list[AudioSegment]:
        """批量创建音频片段记录"""
        segments = []
        for data in segments_data:
            segment = AudioSegment(
                video_id=video_id,
                start_time=data["start_time"],
                end_time=data["end_time"],
                audio_path=data.get("audio_path"),
                asr_text=data.get("asr_text"),
                language=data.get("language"),
                confidence=data.get("confidence"),
            )
            db.add(segment)
            segments.append(segment)
        await db.commit()
        for segment in segments:
            await db.refresh(segment)
        return segments

    async def extract_audio(
        self,
        db: AsyncSession,
        video_id: str,
        format: str = "wav",
        sample_rate: int = 16000,
        channels: int = 1,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """从视频提取完整音频"""
        result = {
            "success": False,
            "audio_path": None,
            "duration": 0,
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
            # 创建音频存储目录
            audio_dir = os.path.join(settings.DOWNLOAD_DIR, "audio", video_id)
            os.makedirs(audio_dir, exist_ok=True)

            # 输出文件路径
            audio_path = os.path.join(audio_dir, f"full_audio.{format}")

            # 使用 ffmpeg 提取音频
            cmd = [
                "ffmpeg",
                "-i", video.file_path,
                "-vn",  # 不包含视频
                "-acodec", format == "wav" and "pcm_s16le" or "libmp3lame",
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-y",
                audio_path,
            ]

            logger.info(f"开始提取音频: {cmd}")
            await asyncio.to_thread(self._run_ffmpeg, cmd)

            # 获取音频时长
            duration = await self._get_audio_duration(audio_path)

            result["success"] = True
            result["audio_path"] = audio_path
            result["duration"] = duration
            logger.info(f"音频提取完成: {audio_path}, 时长: {duration}秒")

            # 创建音频片段记录（完整音频）
            segment = await self.create_audio_segment(
                db=db,
                video_id=video_id,
                start_time=0.0,
                end_time=duration,
                audio_path=audio_path,
            )
            result["segment_id"] = segment.id

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"音频提取失败: {e}")

        return result

    async def extract_audio_segments(
        self,
        db: AsyncSession,
        video_id: str,
        time_segments: list[Dict[str, float]],  # [{"start": 0.0, "end": 10.0}, ...]
        format: str = "wav",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """按时间段提取音频片段"""
        result = {
            "success": False,
            "segments": [],
            "total_segments": 0,
            "error": None,
        }

        # 先提取完整音频
        full_audio_result = await self.extract_audio(db, video_id, format)

        if not full_audio_result["success"]:
            result["error"] = full_audio_result["error"]
            return result

        full_audio_path = full_audio_result["audio_path"]
        audio_dir = os.path.dirname(full_audio_path)

        try:
            segments_data = []

            for i, segment in enumerate(time_segments):
                start_time = segment["start"]
                end_time = segment["end"]

                # 使用 ffmpeg 切割音频
                segment_path = os.path.join(audio_dir, f"segment_{i}_{start_time}_{end_time}.{format}")

                cmd = [
                    "ffmpeg",
                    "-i", full_audio_path,
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-c", "copy",
                    "-y",
                    segment_path,
                ]

                await asyncio.to_thread(self._run_ffmpeg, cmd)

                segments_data.append({
                    "start_time": start_time,
                    "end_time": end_time,
                    "audio_path": segment_path,
                })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(time_segments),
                        "percent": round((i + 1) / len(time_segments) * 100, 2),
                    })

            # 批量创建音频片段记录
            audio_segments = await self.batch_create_audio_segments(db, video_id, segments_data)

            result["success"] = True
            result["segments"] = [s.id for s in audio_segments]
            result["total_segments"] = len(audio_segments)
            logger.info(f"音频片段提取完成: {len(audio_segments)} 个片段")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"音频片段提取失败: {e}")

        return result

    async def perform_asr(
        self,
        db: AsyncSession,
        video_id: str,
        model: str = "base",
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """对视频音频进行 ASR"""
        result = {
            "success": False,
            "segments": [],
            "total_segments": 0,
            "error": None,
        }

        if not self.asr_available:
            result["error"] = "Whisper 未安装，ASR 功能不可用"
            return result

        # 先提取完整音频
        audio_result = await self.extract_audio(db, video_id)

        if not audio_result["success"]:
            result["error"] = audio_result["error"]
            return result

        audio_path = audio_result["audio_path"]

        try:
            # 加载 Whisper 模型
            import whisper
            logger.info(f"加载 Whisper 模型: {model}")

            whisper_model = await asyncio.to_thread(whisper.load_model, model)

            # 执行 ASR
            logger.info(f"开始 ASR: {audio_path}")
            asr_result = await asyncio.to_thread(
                whisper_model.transcribe,
                audio_path,
                language=language,
            )

            # 处理 ASR 结果
            segments_data = []
            for i, segment in enumerate(asr_result.get("segments", [])):
                segments_data.append({
                    "start_time": segment["start"],
                    "end_time": segment["end"],
                    "asr_text": segment["text"],
                    "language": asr_result.get("language", language or "unknown"),
                    "confidence": segment.get("avg_logprob", 0.0),
                    "audio_path": audio_path,
                })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(asr_result.get("segments", [])),
                        "percent": round((i + 1) / len(asr_result["segments"]) * 100, 2),
                    })

            # 批量创建音频片段记录
            audio_segments = await self.batch_create_audio_segments(db, video_id, segments_data)

            result["success"] = True
            result["segments"] = [s.id for s in audio_segments]
            result["total_segments"] = len(audio_segments)
            result["detected_language"] = asr_result.get("language")
            logger.info(f"ASR 完成: {len(audio_segments)} 个片段, 语言: {asr_result.get('language')}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"ASR 失败: {e}")

        return result

    def _run_ffmpeg(self, cmd: list[str]) -> None:
        """运行 ffmpeg 命令"""
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg 错误: {process.stderr}")

    async def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            audio_path,
        ]
        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    async def delete_audio_segments_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有音频片段记录和文件"""
        segments = await self.get_audio_segments_by_video(db, video_id)

        # 删除音频文件
        audio_dir = os.path.join(settings.DOWNLOAD_DIR, "audio", video_id)
        if os.path.exists(audio_dir):
            for segment in segments:
                if segment.audio_path and os.path.exists(segment.audio_path):
                    try:
                        os.remove(segment.audio_path)
                    except Exception:
                        pass
            # 尝试删除目录
            try:
                import shutil
                shutil.rmtree(audio_dir)
            except Exception:
                pass

        # 删除数据库记录
        count = 0
        for segment in segments:
            await db.delete(segment)
            count += 1
        await db.commit()

        return count


# 单例实例
audio_service = AudioService()