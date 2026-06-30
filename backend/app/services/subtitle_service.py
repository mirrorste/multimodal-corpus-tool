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
from app.services.ai.ocr_provider import ocr_provider
from app.services.ai.asr_provider import asr_provider

logger = logging.getLogger(__name__)


class SubtitleService:
    """字幕提取服务 - 从视频提取字幕（内嵌字幕 / OCR硬字幕 / ASR语音）"""

    def __init__(self):
        self.ocr_available = ocr_provider.is_available()
        self.asr_available = asr_provider.is_available()
        logger.info(
            f"SubtitleService 初始化: OCR={'可用' if self.ocr_available else '不可用'}, "
            f"ASR={'可用' if self.asr_available else '不可用'}"
        )

    # ============ 数据库操作 ============

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
        source: Optional[str] = None,
    ) -> List[Subtitle]:
        """获取视频的所有字幕"""
        query = select(Subtitle).where(Subtitle.video_id == video_id)
        if start_time is not None:
            query = query.where(Subtitle.start_time >= start_time)
        if end_time is not None:
            query = query.where(Subtitle.end_time <= end_time)
        if language is not None:
            query = query.where(Subtitle.language == language)
        if source is not None:
            query = query.where(Subtitle.source == source)
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

    async def update_subtitle(
        self,
        db: AsyncSession,
        subtitle_id: str,
        text: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        language: Optional[str] = None,
    ) -> Optional[Subtitle]:
        """更新字幕（人工校正）"""
        subtitle = await self.get_subtitle(db, subtitle_id)
        if not subtitle:
            return None

        if text is not None:
            subtitle.text = text
        if start_time is not None:
            subtitle.start_time = start_time
        if end_time is not None:
            subtitle.end_time = end_time
        if language is not None:
            subtitle.language = language

        await db.commit()
        await db.refresh(subtitle)
        return subtitle

    # ============ 字幕提取主流程 ============

    async def extract_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        source: str = "auto",  # auto / embedded / ocr / asr
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """智能字幕提取入口

        Args:
            source: 字幕来源
                - auto: 自动选择（内嵌 > OCR > ASR）
                - embedded: 仅内嵌字幕轨道
                - ocr: 仅 OCR 硬字幕
                - asr: 仅 ASR 语音识别

        Returns:
            提取结果
        """
        result = {
            "success": False,
            "source_used": None,
            "subtitles": [],
            "total_subtitles": 0,
            "error": None,
        }

        # 获取视频
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()
        if not video:
            result["error"] = "视频不存在"
            return result
        if not video.file_path or not os.path.exists(video.file_path):
            result["error"] = "视频文件不存在"
            return result

        try:
            # auto 模式：按优先级尝试
            if source == "auto":
                # 1. 尝试内嵌字幕
                logger.info("尝试提取内嵌字幕...")
                emb_result = await self.extract_embedded_subtitles(
                    db, video_id, language=language, progress_callback=progress_callback
                )
                if emb_result["success"] and emb_result["total_subtitles"] > 0:
                    result["source_used"] = "embedded"
                    result["success"] = True
                    result["subtitles"] = emb_result["subtitles"]
                    result["total_subtitles"] = emb_result["total_subtitles"]
                    return result

                # 2. 尝试 OCR
                if self.ocr_available:
                    logger.info("无内嵌字幕，尝试 OCR 硬字幕...")
                    ocr_result = await self.extract_ocr_subtitles(
                        db, video_id, language=language, progress_callback=progress_callback
                    )
                    if ocr_result["success"] and ocr_result["total_subtitles"] > 0:
                        result["source_used"] = "OCR"
                        result["success"] = True
                        result["subtitles"] = ocr_result["subtitles"]
                        result["total_subtitles"] = ocr_result["total_subtitles"]
                        return result

                # 3. 尝试 ASR
                if self.asr_available:
                    logger.info("无 OCR 字幕，尝试 ASR 语音识别...")
                    asr_result = await self.extract_asr_subtitles(
                        db, video_id, language=language, progress_callback=progress_callback
                    )
                    if asr_result["success"]:
                        result["source_used"] = "asr"
                        result["success"] = True
                        result["subtitles"] = asr_result["subtitles"]
                        result["total_subtitles"] = asr_result["total_subtitles"]
                        return result

                result["error"] = "未找到可用字幕（内嵌/OCR/ASR 均失败）"
                return result

            # 指定来源模式
            if source == "embedded":
                return await self.extract_embedded_subtitles(
                    db, video_id, language=language, progress_callback=progress_callback
                )
            elif source == "ocr":
                return await self.extract_ocr_subtitles(
                    db, video_id, language=language, progress_callback=progress_callback
                )
            elif source == "asr":
                return await self.extract_asr_subtitles(
                    db, video_id, language=language, progress_callback=progress_callback
                )
            else:
                result["error"] = f"不支持的 source: {source}"
                return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"字幕提取失败: {e}")
            return result

    # ============ 1. 内嵌字幕提取 ============

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

        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()

        if not video:
            result["error"] = "视频不存在"
            return result
        if not video.file_path or not os.path.exists(video.file_path):
            result["error"] = "视频文件不存在"
            return result

        try:
            track_info = await self._get_subtitle_tracks(video.file_path)
            if not track_info:
                result["error"] = "视频没有内嵌字幕轨道"
                return result

            # 字幕输出路径
            subtitle_output = os.path.join(
                settings.DOWNLOAD_DIR, "subtitles", f"{video_id}_embedded.srt"
            )
            os.makedirs(os.path.dirname(subtitle_output), exist_ok=True)

            # 提取所有字幕轨道
            track_count = track_info.get("count", 1)
            all_subtitles = []

            for track_index in range(track_count):
                output_file = subtitle_output.replace(".srt", f"_track{track_index}.srt")

                cmd = [
                    "ffmpeg",
                    "-i", video.file_path,
                    "-map", f"0:s:{track_index}",
                    "-y",
                    output_file,
                ]

                try:
                    await asyncio.to_thread(self._run_ffmpeg, cmd)
                except Exception as e:
                    logger.warning(f"提取轨道 {track_index} 失败: {e}")
                    continue

                if not os.path.exists(output_file):
                    continue

                # 解析字幕
                track_lang = (
                    language
                    or track_info.get("tracks", [{}])[track_index].get("language")
                    or "unknown"
                )
                parsed = await self._parse_srt_file(output_file)
                for sub in parsed:
                    sub["language"] = track_lang
                    sub["source"] = "embedded"
                    sub["confidence"] = 1.0
                    all_subtitles.append(sub)

            if not all_subtitles:
                result["error"] = "未能解析到任何字幕内容"
                return result

            # 按时间排序
            all_subtitles.sort(key=lambda x: x["start_time"])

            # 批量创建记录
            subtitles = await self.batch_create_subtitles(db, video_id, all_subtitles)

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

            if not streams:
                return None

            tracks = []
            for s in streams:
                tracks.append({
                    "index": s.get("index"),
                    "language": s.get("tags", {}).get("language", "unknown"),
                    "codec": s.get("codec_name"),
                    "title": s.get("tags", {}).get("title", ""),
                })

            return {
                "count": len(tracks),
                "tracks": tracks,
                "language": tracks[0].get("language", "unknown"),
                "codec": tracks[0].get("codec_name"),
            }
        except Exception:
            return None

    # ============ 2. OCR 硬字幕提取 ============

    async def extract_ocr_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """使用 OCR 从帧中提取硬字幕（集成 OCRProvider）"""
        result = {
            "success": False,
            "subtitles": [],
            "total_subtitles": 0,
            "error": None,
        }

        # 获取有字幕的帧
        frames_result = await db.execute(
            select(Frame)
            .where(Frame.video_id == video_id, Frame.has_subtitle == True)  # noqa: E712
            .order_by(Frame.timestamp)
        )
        frames = frames_result.scalars().all()

        if not frames:
            # 回退：使用全部帧
            frames_result = await db.execute(
                select(Frame)
                .where(Frame.video_id == video_id)
                .order_by(Frame.timestamp)
            )
            frames = frames_result.scalars().all()

        if not frames:
            result["error"] = "没有可用的帧，请先提取帧"
            return result

        if not self.ocr_available:
            result["error"] = "OCR 服务不可用"
            return result

        try:
            subtitles_data = []

            for i, frame in enumerate(frames):
                if frame.image_path and os.path.exists(frame.image_path):
                    ocr_result = await self._ocr_frame(
                        frame.image_path, language=language
                    )

                    if ocr_result and ocr_result.get("text"):
                        # 计算该帧字幕的结束时间（取到下一帧时间戳）
                        end_time = self._infer_end_time(frames, i)
                        subtitles_data.append({
                            "start_time": frame.timestamp,
                            "end_time": end_time,
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
                        "phase": "ocr_recognition",
                    })

            # 字幕时间轴校正与合并
            subtitles_data = self._merge_adjacent_subtitles(subtitles_data)
            subtitles_data = self._refine_subtitle_boundaries(subtitles_data)
            subtitles_data = self._split_long_subtitles(subtitles_data)

            # 批量入库
            subtitles = await self.batch_create_subtitles(db, video_id, subtitles_data)

            result["success"] = True
            result["subtitles"] = [s.id for s in subtitles]
            result["total_subtitles"] = len(subtitles)
            logger.info(f"OCR 字幕提取完成: {len(subtitles)} 条")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"OCR 字幕提取失败: {e}")

        return result

    def _infer_end_time(self, frames: List[Frame], current_index: int) -> float:
        """根据相邻帧推断字幕结束时间"""
        if current_index + 1 < len(frames):
            # 取下一帧的时间戳作为结束时间
            return frames[current_index + 1].timestamp
        # 最后一帧：默认延长 2 秒
        return frames[current_index].timestamp + 2.0

    async def _ocr_frame(
        self,
        frame_path: str,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """对单帧进行 OCR（使用 OCRProvider 统一接口）"""
        try:
            ocr_result = await ocr_provider.recognize(frame_path)

            if not ocr_result.get("success"):
                return None

            text = ocr_result.get("text", "").strip()
            if not text:
                return None

            # 多语言检测
            detected_lang = ocr_result.get("language")
            if language and detected_lang and detected_lang != language:
                # 强制使用指定语言
                lang = language
            else:
                lang = detected_lang or self._detect_text_language(text)

            return {
                "text": text,
                "confidence": ocr_result.get("confidence", 0.5),
                "language": lang,
                "segments": ocr_result.get("segments", []),
            }
        except Exception as e:
            logger.warning(f"OCR 处理失败: {e}")
            return None

    # ============ 3. ASR 语音识别提取 ============

    async def extract_asr_subtitles(
        self,
        db: AsyncSession,
        video_id: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """使用 ASR 从音频中提取字幕（集成 ASRProvider）"""
        result = {
            "success": False,
            "subtitles": [],
            "total_subtitles": 0,
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

        if not self.asr_available:
            result["error"] = "ASR 服务不可用"
            return result

        try:
            # 提取音频
            if progress_callback:
                progress_callback({
                    "current": 0,
                    "total": 100,
                    "percent": 0,
                    "phase": "extracting_audio",
                })

            audio_output = os.path.join(
                settings.DOWNLOAD_DIR, "audio", f"{video_id}.wav"
            )
            os.makedirs(os.path.dirname(audio_output), exist_ok=True)

            cmd = [
                "ffmpeg",
                "-i", video.file_path,
                "-vn",  # 不处理视频
                "-acodec", "pcm_s16le",  # PCM 16-bit
                "-ar", "16000",  # 16kHz 采样率（Whisper 推荐）
                "-ac", "1",  # 单声道
                "-y",
                audio_output,
            ]
            await asyncio.to_thread(self._run_ffmpeg, cmd)

            if progress_callback:
                progress_callback({
                    "current": 20,
                    "total": 100,
                    "percent": 20,
                    "phase": "asr_transcribing",
                })

            # 调用 ASR
            asr_result = await asr_provider.transcribe(
                audio_output, language=language
            )

            if not asr_result.get("success"):
                result["error"] = asr_result.get("error", "ASR 识别失败")
                return result

            # 转换 ASR 段落为字幕
            segments = asr_result.get("segments", [])
            detected_lang = asr_result.get("language", language or "unknown")

            subtitles_data = []
            for seg in segments:
                text = seg.get("text", "").strip()
                if not text:
                    continue
                subtitles_data.append({
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "text": text,
                    "language": detected_lang,
                    "source": "asr",
                    "confidence": asr_result.get("confidence", 0.9),
                })

            # 分句优化
            subtitles_data = self._split_long_subtitles(subtitles_data)

            if progress_callback:
                progress_callback({
                    "current": 90,
                    "total": 100,
                    "percent": 90,
                    "phase": "saving_subtitles",
                })

            # 批量入库
            subtitles = await self.batch_create_subtitles(db, video_id, subtitles_data)

            if progress_callback:
                progress_callback({
                    "current": 100,
                    "total": 100,
                    "percent": 100,
                    "phase": "completed",
                })

            result["success"] = True
            result["subtitles"] = [s.id for s in subtitles]
            result["total_subtitles"] = len(subtitles)
            logger.info(f"ASR 字幕提取完成: {len(subtitles)} 条")

            # 清理临时音频
            try:
                os.remove(audio_output)
            except Exception:
                pass

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"ASR 字幕提取失败: {e}")

        return result

    # ============ 字幕后处理 ============

    def _merge_adjacent_subtitles(
        self,
        subtitles_data: List[Dict[str, Any]],
        threshold: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """合并相邻的相同字幕

        当相邻两条字幕文本完全相同且时间间隔 < threshold 时合并
        """
        if not subtitles_data:
            return []

        merged = []
        current = dict(subtitles_data[0])  # 复制避免修改原数据

        for i in range(1, len(subtitles_data)):
            next_sub = subtitles_data[i]

            # 文本相同 + 时间相邻 -> 合并
            is_same_text = next_sub["text"] == current["text"]
            is_close = next_sub["start_time"] - current["end_time"] <= threshold

            if is_same_text and is_close:
                current["end_time"] = next_sub["end_time"]
                current["confidence"] = max(
                    current.get("confidence", 0),
                    next_sub.get("confidence", 0),
                )
            else:
                merged.append(current)
                current = dict(next_sub)

        merged.append(current)
        return merged

    def _refine_subtitle_boundaries(
        self,
        subtitles_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """字幕时间轴校正

        1. 修正负值持续时间
        2. 设置最小持续时间 0.5 秒
        3. 设置最大持续时间 8 秒
        4. 处理重叠区间
        """
        refined = []
        for sub in subtitles_data:
            new_sub = dict(sub)
            duration = new_sub["end_time"] - new_sub["start_time"]

            # 修正负值
            if duration < 0:
                new_sub["end_time"] = new_sub["start_time"] + 0.5

            # 最小持续时间
            duration = new_sub["end_time"] - new_sub["start_time"]
            if duration < 0.5:
                new_sub["end_time"] = new_sub["start_time"] + 0.5

            # 最大持续时间
            if duration > 8.0:
                new_sub["end_time"] = new_sub["start_time"] + 8.0

            refined.append(new_sub)

        # 处理重叠：相邻字幕 end > 下一个 start 时，将当前 end 调整为下一个 start
        for i in range(len(refined) - 1):
            if refined[i]["end_time"] > refined[i + 1]["start_time"]:
                refined[i]["end_time"] = refined[i + 1]["start_time"]

        return refined

    def _split_long_subtitles(
        self,
        subtitles_data: List[Dict[str, Any]],
        max_length: int = 50,
    ) -> List[Dict[str, Any]]:
        """将过长字幕按标点符号分句

        Args:
            max_length: 单条字幕最大字符数
        """
        if not subtitles_data:
            return []

        split_punct = "。！？!?\n"  # 中英文分句标点

        result = []
        for sub in subtitles_data:
            text = sub.get("text", "").strip()
            if len(text) <= max_length:
                result.append(sub)
                continue

            # 在标点处分句
            sentences = self._split_by_punctuation(text, split_punct)
            if len(sentences) <= 1:
                result.append(sub)
                continue

            # 按时间等分各句
            total_duration = sub["end_time"] - sub["start_time"]
            per_duration = total_duration / len(sentences)

            for idx, sent in enumerate(sentences):
                sent = sent.strip()
                if not sent:
                    continue
                new_sub = dict(sub)
                new_sub["text"] = sent
                new_sub["start_time"] = sub["start_time"] + idx * per_duration
                new_sub["end_time"] = sub["start_time"] + (idx + 1) * per_duration
                result.append(new_sub)

        return result

    def _split_by_punctuation(self, text: str, punct: str) -> List[str]:
        """根据标点分句"""
        result = []
        current = ""

        for ch in text:
            current += ch
            if ch in punct and current.strip():
                result.append(current.strip())
                current = ""

        if current.strip():
            result.append(current.strip())

        return result

    def _detect_text_language(self, text: str) -> str:
        """简单文本语言检测"""
        if not text:
            return "unknown"

        # 统计各类字符
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        japanese = sum(1 for c in text if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        korean = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
        latin = sum(1 for c in text if c.isascii() and c.isalpha())

        total = chinese + japanese + korean + latin
        if total == 0:
            return "unknown"

        if japanese / total > 0.3:
            return "ja"
        if korean / total > 0.3:
            return "ko"
        if chinese / total > 0.5:
            return "zh"
        if latin / total > 0.7:
            return "en"

        # 混合语言
        if chinese > 0 and latin > 0:
            return "mixed"

        return "unknown"

    # ============ SRT 文件解析 ============

    async def _parse_srt_file(self, srt_path: str) -> List[Dict[str, Any]]:
        """解析 SRT 字幕文件"""
        subtitles = []
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # SRT 格式：序号 + 时间戳 + 文本
            pattern = r"(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s+(.*?)(?=\n\n|\n$)"
            matches = re.findall(pattern, content, re.DOTALL)

            for match in matches:
                start_time = self._srt_time_to_seconds(match[1])
                end_time = self._srt_time_to_seconds(match[2])
                text = match[3].strip().replace("\n", " ")

                if text:  # 过滤空字幕
                    subtitles.append({
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
            int(hours) * 3600
            + int(minutes) * 60
            + int(seconds)
            + int(milliseconds) / 1000
        )

    # ============ 工具方法 ============

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
