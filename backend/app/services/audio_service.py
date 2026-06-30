"""音频提取服务"""
import asyncio
import os
import subprocess
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.models.audio_segment import AudioSegment
from app.models.video import Video
from app.models.subtitle import Subtitle
from app.core.config import settings
from app.services.ai.asr_provider import asr_provider

logger = logging.getLogger(__name__)


class AudioService:
    """音频提取服务 - 从视频提取音频并进行 ASR 语音识别"""

    def __init__(self):
        self.asr_available = asr_provider.is_available()
        logger.info(f"AudioService 初始化: ASR={'可用' if self.asr_available else '不可用'}")

    # ============ 数据库操作 ============

    async def get_audio_segment(
        self, db: AsyncSession, segment_id: str
    ) -> Optional[AudioSegment]:
        """获取单个音频片段"""
        result = await db.execute(
            select(AudioSegment).where(AudioSegment.id == segment_id)
        )
        return result.scalar_one_or_none()

    async def get_audio_segments_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        has_asr: Optional[bool] = None,
    ) -> List[AudioSegment]:
        """获取视频的所有音频片段"""
        query = select(AudioSegment).where(AudioSegment.video_id == video_id)
        if start_time is not None:
            query = query.where(AudioSegment.start_time >= start_time)
        if end_time is not None:
            query = query.where(AudioSegment.end_time <= end_time)
        if has_asr is not None:
            if has_asr:
                query = query.where(AudioSegment.asr_text.isnot(None))
            else:
                query = query.where(AudioSegment.asr_text.is_(None))
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
        segments_data: List[Dict[str, Any]],
    ) -> List[AudioSegment]:
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

    async def update_audio_segment(
        self,
        db: AsyncSession,
        segment_id: str,
        asr_text: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[AudioSegment]:
        """更新音频片段（ASR 结果或人工校正）"""
        segment = await self.get_audio_segment(db, segment_id)
        if not segment:
            return None

        if asr_text is not None:
            segment.asr_text = asr_text
        if language is not None:
            segment.language = language

        await db.commit()
        await db.refresh(segment)
        return segment

    # ============ 音频提取主流程 ============

    async def extract_audio(
        self,
        db: AsyncSession,
        video_id: str,
        format: str = "wav",
        sample_rate: int = 16000,
        channels: int = 1,
        denoise: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """从视频提取完整音频

        Args:
            format: 音频格式（wav/mp3/flac）
            sample_rate: 采样率（默认 16000，Whisper 推荐）
            channels: 声道数（默认 1 单声道）
            denoise: 是否降噪处理
        """
        result = {
            "success": False,
            "audio_path": None,
            "duration": 0,
            "error": None,
        }

        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()

        if not video:
            result["error"] = "视频不存在"
            return result
        if not video.file_path or not os.path.exists(video.file_path):
            result["error"] = "视频文件不存在"
            return result

        try:
            audio_dir = os.path.join(settings.DOWNLOAD_DIR, "audio", video_id)
            os.makedirs(audio_dir, exist_ok=True)

            # 中间文件（未降噪）
            raw_audio = os.path.join(audio_dir, f"raw_audio.{format}")
            # 最终文件（可能降噪）
            audio_path = os.path.join(audio_dir, f"full_audio.{format}")

            if progress_callback:
                progress_callback({
                    "current": 0, "total": 100, "percent": 0, "phase": "extracting_raw_audio"
                })

            # 第一步：提取原始音频
            acodec = "pcm_s16le" if format == "wav" else "libmp3lame" if format == "mp3" else "flac"
            cmd = [
                "ffmpeg",
                "-i", video.file_path,
                "-vn",
                "-acodec", acodec,
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-y",
                raw_audio,
            ]
            await asyncio.to_thread(self._run_ffmpeg, cmd)

            if progress_callback:
                progress_callback({
                    "current": 30, "total": 100, "percent": 30, "phase": "processing_audio"
                })

            # 第二步：降噪处理
            if denoise:
                audio_path = raw_audio.replace(f".{format}", "_denoised.{format}")
                noise_reduced = await self._apply_denoise(raw_audio, audio_path, format)
                if not noise_reduced:
                    # 降噪失败，使用原始音频
                    audio_path = raw_audio
            else:
                audio_path = raw_audio

            # 获取音频时长
            duration = await self._get_audio_duration(audio_path)

            if progress_callback:
                progress_callback({
                    "current": 90, "total": 100, "percent": 90, "phase": "saving_record"
                })

            # 创建音频片段记录（完整音频）
            segment = await self.create_audio_segment(
                db=db,
                video_id=video_id,
                start_time=0.0,
                end_time=duration,
                audio_path=audio_path,
            )

            if progress_callback:
                progress_callback({
                    "current": 100, "total": 100, "percent": 100, "phase": "completed"
                })

            result["success"] = True
            result["audio_path"] = audio_path
            result["duration"] = duration
            result["segment_id"] = segment.id
            logger.info(f"音频提取完成: {audio_path}, 时长: {duration}秒, 降噪: {denoise}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"音频提取失败: {e}")

        return result

    async def _apply_denoise(
        self, input_path: str, output_path: str, format: str
    ) -> bool:
        """应用音频降噪

        使用 FFmpeg 的音频滤镜链进行降噪：
        - highpass: 去除低频噪声
        - lowpass: 去除高频噪声
        - afftdn: 自适应降噪（如果可用）
        """
        try:
            # 方法1: 尝试使用 afftdn 自适应降噪
            cmd_denoise = [
                "ffmpeg",
                "-i", input_path,
                "-af", "afftdn=n=noise=ambient,dynaudnorm=f=150",
                "-y",
                output_path,
            ]
            proc = await asyncio.to_thread(
                subprocess.run, cmd_denoise, capture_output=True
            )
            if proc.returncode == 0 and os.path.exists(output_path):
                return True

            # 方法2: 简单的高通+低通滤波
            cmd_simple = [
                "ffmpeg",
                "-i", input_path,
                "-af", "highpass=f=200,lowpass=f=3000",
                "-y",
                output_path,
            ]
            proc = await asyncio.to_thread(
                subprocess.run, cmd_simple, capture_output=True
            )
            if proc.returncode == 0 and os.path.exists(output_path):
                return True

            return False
        except Exception as e:
            logger.warning(f"音频降噪失败: {e}")
            return False

    # ============ 按时间戳提取音频片段 ============

    async def extract_audio_segments(
        self,
        db: AsyncSession,
        video_id: str,
        time_segments: List[Dict[str, float]],
        format: str = "wav",
        denoise: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """按时间段提取音频片段

        Args:
            time_segments: 时间段列表 [{"start": 0.0, "end": 10.0}, ...]
        """
        result = {
            "success": False,
            "segments": [],
            "total_segments": 0,
            "error": None,
        }

        # 先提取完整音频（用于切割）
        full_audio_result = await self.extract_audio(db, video_id, format=format, denoise=denoise)
        if not full_audio_result["success"]:
            result["error"] = full_audio_result["error"]
            return result

        full_audio_path = full_audio_result["audio_path"]
        audio_dir = os.path.dirname(full_audio_path)

        try:
            segments_data = []

            for i, seg in enumerate(time_segments):
                start_time = seg["start"]
                end_time = seg["end"]

                if end_time <= start_time:
                    continue

                segment_path = os.path.join(
                    audio_dir, f"segment_{i}_{start_time:.2f}_{end_time:.2f}.{format}"
                )

                # 使用 ffmpeg 切割音频
                cmd = [
                    "ffmpeg",
                    "-i", full_audio_path,
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-acodec", "copy" if format == "wav" else "libmp3lame",
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
                        "phase": "extracting_segments",
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

    async def extract_audio_by_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        format: str = "wav",
        denoise: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """按字幕时间戳提取音频片段

        提取每个字幕对应时间段的音频
        """
        # 获取字幕
        subtitles = await db.execute(
            select(Subtitle)
            .where(Subtitle.video_id == video_id)
            .order_by(Subtitle.start_time)
        )
        subtitles = subtitles.scalars().all()

        if not subtitles:
            return {
                "success": False,
                "error": "没有可用的字幕",
                "segments": [],
                "total_segments": 0,
            }

        # 构建时间段
        time_segments = [
            {"start": sub.start_time, "end": sub.end_time}
            for sub in subtitles
        ]

        # 提取音频片段
        result = await self.extract_audio_segments(
            db=db,
            video_id=video_id,
            time_segments=time_segments,
            format=format,
            denoise=denoise,
            progress_callback=progress_callback,
        )

        # 为每个片段关联字幕文本
        if result["success"]:
            segments = await self.get_audio_segments_by_video(db, video_id)
            for i, seg in enumerate(segments):
                if i < len(subtitles):
                    seg.asr_text = subtitles[i].text
                    seg.language = subtitles[i].language
                    await db.commit()

        return result

    # ============ ASR 语音识别 ============

    async def perform_asr(
        self,
        db: AsyncSession,
        video_id: str,
        language: Optional[str] = None,
        denoise: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """对视频音频进行 ASR 语音识别（集成 ASRProvider）

        使用 ASRProvider 统一接口，支持本地 Whisper 和云端 API 自动降级
        """
        result = {
            "success": False,
            "segments": [],
            "total_segments": 0,
            "detected_language": None,
            "error": None,
        }

        if not self.asr_available:
            result["error"] = "ASR 服务不可用"
            return result

        # 先提取音频
        if progress_callback:
            progress_callback({
                "current": 0, "total": 100, "percent": 0, "phase": "extracting_audio"
            })

        audio_result = await self.extract_audio(db, video_id, denoise=denoise)
        if not audio_result["success"]:
            result["error"] = audio_result["error"]
            return result

        audio_path = audio_result["audio_path"]

        if progress_callback:
            progress_callback({
                "current": 20, "total": 100, "percent": 20, "phase": "asr_transcribing"
            })

        try:
            # 调用 ASRProvider 进行语音识别
            asr_result = await asr_provider.transcribe(audio_path, language=language)

            if not asr_result.get("success"):
                result["error"] = asr_result.get("error", "ASR 识别失败")
                return result

            # 处理 ASR 结果，转换为音频片段
            asr_segments = asr_result.get("segments", [])
            detected_lang = asr_result.get("language", language or "unknown")

            segments_data = []
            for seg in asr_segments:
                text = seg.get("text", "").strip()
                if not text:
                    continue
                segments_data.append({
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "asr_text": text,
                    "language": detected_lang,
                    "confidence": asr_result.get("confidence", 0.9),
                    "audio_path": audio_path,
                })

            if progress_callback:
                progress_callback({
                    "current": 80, "total": 100, "percent": 80, "phase": "saving_segments"
                })

            # 批量创建音频片段记录
            audio_segments = await self.batch_create_audio_segments(db, video_id, segments_data)

            if progress_callback:
                progress_callback({
                    "current": 100, "total": 100, "percent": 100, "phase": "completed"
                })

            result["success"] = True
            result["segments"] = [s.id for s in audio_segments]
            result["total_segments"] = len(audio_segments)
            result["detected_language"] = detected_lang
            result["provider"] = asr_result.get("provider", "unknown")
            logger.info(
                f"ASR 完成: {len(audio_segments)} 个片段, 语言: {detected_lang}, "
                f"Provider: {asr_result.get('provider')}"
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"ASR 失败: {e}")

        return result

    async def translate_audio(
        self,
        db: AsyncSession,
        video_id: str,
        target_language: str = "en",
        denoise: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """对视频音频进行语音翻译

        先 ASR 识别，再（可选）翻译
        """
        result = {
            "success": False,
            "segments": [],
            "total_segments": 0,
            "detected_language": None,
            "error": None,
        }

        if not self.asr_available:
            result["error"] = "ASR 服务不可用"
            return result

        # 先提取音频
        audio_result = await self.extract_audio(db, video_id, denoise=denoise)
        if not audio_result["success"]:
            result["error"] = audio_result["error"]
            return result

        audio_path = audio_result["audio_path"]

        try:
            # 调用 ASRProvider 进行语音翻译
            asr_result = await asr_provider.translate(audio_path, target_language=target_language)

            if not asr_result.get("success"):
                result["error"] = asr_result.get("error", "翻译失败")
                return result

            # 处理结果
            asr_segments = asr_result.get("segments", [])
            detected_lang = asr_result.get("detected_language", "unknown")

            segments_data = []
            for seg in asr_segments:
                text = seg.get("text", "").strip()
                if not text:
                    continue
                segments_data.append({
                    "start_time": seg.get("start", 0),
                    "end_time": seg.get("end", 0),
                    "asr_text": text,
                    "language": target_language,
                    "confidence": asr_result.get("confidence", 0.9),
                    "audio_path": audio_path,
                })

            # 批量创建
            audio_segments = await self.batch_create_audio_segments(db, video_id, segments_data)

            result["success"] = True
            result["segments"] = [s.id for s in audio_segments]
            result["total_segments"] = len(audio_segments)
            result["detected_language"] = detected_lang
            result["target_language"] = target_language
            logger.info(f"语音翻译完成: {len(audio_segments)} 个片段")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"语音翻译失败: {e}")

        return result

    # ============ 工具方法 ============

    def _run_ffmpeg(self, cmd: List[str]) -> None:
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

        # 收集需要删除的目录
        audio_dirs = set()
        for segment in segments:
            if segment.audio_path:
                audio_dirs.add(os.path.dirname(segment.audio_path))

        # 删除数据库记录
        count = 0
        for segment in segments:
            await db.delete(segment)
            count += 1
        await db.commit()

        # 删除音频文件目录
        for audio_dir in audio_dirs:
            if os.path.exists(audio_dir):
                try:
                    import shutil
                    shutil.rmtree(audio_dir)
                except Exception:
                    pass

        return count


# 单例实例
audio_service = AudioService()
