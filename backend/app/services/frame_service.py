"""帧提取服务"""
import asyncio
import os
import subprocess
import re
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.frame import Frame
from app.models.video import Video
from app.core.config import settings

logger = logging.getLogger(__name__)


class FrameService:
    """帧提取服务 - 从视频中提取关键帧"""

    def __init__(self):
        os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.DOWNLOAD_DIR, "frames"), exist_ok=True)

    async def get_frame(self, db: AsyncSession, frame_id: str) -> Optional[Frame]:
        """获取单个帧"""
        result = await db.execute(select(Frame).where(Frame.id == frame_id))
        return result.scalar_one_or_none()

    async def get_frames_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[Frame]:
        """获取视频的所有帧"""
        query = select(Frame).where(Frame.video_id == video_id)
        if start_time is not None:
            query = query.where(Frame.timestamp >= start_time)
        if end_time is not None:
            query = query.where(Frame.timestamp <= end_time)
        query = query.order_by(Frame.timestamp)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_frame(
        self,
        db: AsyncSession,
        video_id: str,
        timestamp: float,
        frame_number: Optional[int] = None,
        image_path: Optional[str] = None,
        has_subtitle: bool = False,
        quality_score: Optional[float] = None,
    ) -> Frame:
        """创建帧记录"""
        frame = Frame(
            video_id=video_id,
            timestamp=timestamp,
            frame_number=frame_number,
            image_path=image_path,
            has_subtitle=has_subtitle,
            quality_score=quality_score,
        )
        db.add(frame)
        await db.commit()
        await db.refresh(frame)
        return frame

    async def batch_create_frames(
        self,
        db: AsyncSession,
        video_id: str,
        frames_data: list[Dict[str, Any]],
    ) -> list[Frame]:
        """批量创建帧记录"""
        frames = []
        for data in frames_data:
            frame = Frame(
                video_id=video_id,
                timestamp=data["timestamp"],
                frame_number=data.get("frame_number"),
                image_path=data.get("image_path"),
                has_subtitle=data.get("has_subtitle", False),
                quality_score=data.get("quality_score"),
            )
            db.add(frame)
            frames.append(frame)
        await db.commit()
        for frame in frames:
            await db.refresh(frame)
        return frames

    async def extract_frames(
        self,
        db: AsyncSession,
        video_id: str,
        fps: float = 1.0,  # 每秒提取帧数
        quality: int = 2,  # 图片质量 1-5，越小质量越高
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """从视频提取帧"""
        result = {
            "success": False,
            "frames": [],
            "total_frames": 0,
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
            # 创建帧存储目录
            frame_dir = os.path.join(settings.DOWNLOAD_DIR, "frames", video_id)
            os.makedirs(frame_dir, exist_ok=True)

            # 使用 ffmpeg 提取帧
            output_pattern = os.path.join(frame_dir, "frame_%06d.jpg")

            # 构建 ffmpeg 命令
            cmd = [
                "ffmpeg",
                "-i", video.file_path,
                "-vf", f"fps={fps}",
                "-q:v", str(quality),
                "-y",  # 覆盖已存在的文件
                output_pattern,
            ]

            logger.info(f"开始提取帧: {cmd}")
            await asyncio.to_thread(self._run_ffmpeg, cmd)

            # 获取提取的帧文件列表
            frame_files = sorted(
                [f for f in os.listdir(frame_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            )

            # 计算每帧的时间戳
            video_fps = fps
            video_duration = video.duration or await self._get_video_duration(video.file_path)

            frames_data = []
            for i, frame_file in enumerate(frame_files):
                timestamp = i / video_fps
                frame_number = i + 1
                image_path = os.path.join(frame_dir, frame_file)

                # 计算帧质量分数（简单方法：文件大小）
                file_size = os.path.getsize(image_path)
                quality_score = min(file_size / 100000, 1.0)  # 简单的质量估算

                frames_data.append({
                    "timestamp": timestamp,
                    "frame_number": frame_number,
                    "image_path": image_path,
                    "has_subtitle": False,  # 后续由字幕检测更新
                    "quality_score": quality_score,
                })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(frame_files),
                        "percent": round((i + 1) / len(frame_files) * 100, 2),
                    })

            # 批量创建帧记录
            frames = await self.batch_create_frames(db, video_id, frames_data)

            result["success"] = True
            result["frames"] = [f.id for f in frames]
            result["total_frames"] = len(frames)
            logger.info(f"帧提取完成: {len(frames)} 帧")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"帧提取失败: {e}")

        return result

    def _run_ffmpeg(self, cmd: list[str]) -> None:
        """运行 ffmpeg 命令"""
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg 错误: {process.stderr}")

    async def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            video_path,
        ]
        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    async def extract_key_frames(
        self,
        db: AsyncSession,
        video_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """提取关键帧（场景变化帧）"""
        result = await self.extract_frames(
            db=db,
            video_id=video_id,
            fps=0.5,  # 每2秒提取一帧作为关键帧
            quality=1,
            progress_callback=progress_callback,
        )
        return result

    async def detect_subtitle_frames(
        self,
        db: AsyncSession,
        video_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测包含字幕的帧（基于图像区域亮度变化）"""
        frames = await self.get_frames_by_video(db, video_id)
        result = {
            "success": False,
            "subtitle_frames": [],
            "total_frames": len(frames),
            "error": None,
        }

        try:
            subtitle_frames = []
            for i, frame in enumerate(frames):
                if frame.image_path and os.path.exists(frame.image_path):
                    # 简单的字幕检测：检查帧是否存在有效路径
                    # 实际应使用 OCR 或图像处理检测字幕区域
                    has_subtitle = await self._detect_subtitle_in_frame(frame.image_path)

                    if has_subtitle:
                        frame.has_subtitle = True
                        subtitle_frames.append(frame.id)

                    if progress_callback:
                        progress_callback({
                            "current": i + 1,
                            "total": len(frames),
                            "percent": round((i + 1) / len(frames) * 100, 2),
                        })

            await db.commit()

            result["success"] = True
            result["subtitle_frames"] = subtitle_frames
            logger.info(f"字幕帧检测完成: {len(subtitle_frames)} 帧")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"字幕帧检测失败: {e}")

        return result

    async def _detect_subtitle_in_frame(self, frame_path: str) -> bool:
        """检测单帧是否包含字幕（占位实现）"""
        # 实际实现需要：
        # 1. 使用图像处理检测字幕区域
        # 2. 或使用 OCR 模型预检测
        # 这里返回 True 以便后续 OCR 处理
        return True

    async def extract_subtitle_frames(
        self,
        db: AsyncSession,
        video_id: str,
        fps: float = 1.0,
        quality: int = 2,
        margin: float = 0.5,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """提取包含字幕的画面帧

        策略：
        1. 优先检测内嵌字幕轨道，使用字幕时间戳提取帧
        2. 如果没有内嵌字幕，使用图像处理检测字幕区域

        Args:
            db: 数据库会话
            video_id: 视频ID
            fps: 每秒提取帧数
            quality: 图片质量 1-5，越小质量越高
            margin: 字幕时间戳前后扩展边距（秒）
            progress_callback: 进度回调函数
        """
        result = {
            "success": False,
            "subtitle_frames": [],
            "total_frames": 0,
            "has_embedded_subtitles": False,
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
            # 步骤1: 尝试获取内嵌字幕轨道
            subtitle_timestamps = await self._get_subtitle_timestamps(video.file_path)

            if subtitle_timestamps:
                result["has_embedded_subtitles"] = True
                logger.info(f"检测到内嵌字幕: {len(subtitle_timestamps)} 个时间点")

                # 步骤2: 基于字幕时间戳提取帧
                frames_data = await self._extract_frames_at_timestamps(
                    video=video,
                    timestamps=subtitle_timestamps,
                    margin=margin,
                    fps=fps,
                    quality=quality,
                    progress_callback=progress_callback,
                )
            else:
                logger.info("没有检测到内嵌字幕，使用图像处理检测字幕区域")
                # 步骤2': 全量提取帧并用图像处理检测字幕
                frames_data = await self._extract_frames_with_subtitle_detection(
                    video=video,
                    fps=fps,
                    quality=quality,
                    progress_callback=progress_callback,
                )

            # 步骤3: 批量创建帧记录
            frames = await self.batch_create_frames(db, video_id, frames_data)

            result["success"] = True
            result["subtitle_frames"] = [f.id for f in frames]
            result["total_frames"] = len(frames)
            logger.info(f"字幕帧提取完成: {len(frames)} 帧")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"字幕帧提取失败: {e}")

        return result

    async def _get_subtitle_timestamps(self, video_path: str) -> List[Dict[str, float]]:
        """获取视频内嵌字幕的时间戳列表"""
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
                return []

            # 检查是否有字幕轨道
            subtitle_stream = streams[0]

            # 尝试提取字幕文件
            subtitle_output = os.path.join(
                settings.DOWNLOAD_DIR,
                "subtitles",
                f"temp_subtitle_{os.getpid()}.srt"
            )
            os.makedirs(os.path.dirname(subtitle_output), exist_ok=True)

            extract_cmd = [
                "ffmpeg",
                "-i", video_path,
                "-map", f"0:s:{subtitle_stream.get('index', 0)}",
                "-y",
                subtitle_output,
            ]

            subprocess.run(extract_cmd, capture_output=True, text=True)

            if not os.path.exists(subtitle_output):
                return []

            # 解析 SRT 文件获取时间戳
            timestamps = self._parse_srt_timestamps(subtitle_output)

            # 清理临时文件
            try:
                os.remove(subtitle_output)
            except Exception:
                pass

            return timestamps

        except Exception as e:
            logger.warning(f"获取字幕时间戳失败: {e}")
            return []

    def _parse_srt_timestamps(self, srt_path: str) -> List[Dict[str, float]]:
        """解析 SRT 文件提取字幕时间戳"""
        timestamps = []
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # SRT 格式解析
            pattern = r"(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
            matches = re.findall(pattern, content)

            for match in matches:
                start_time = self._srt_time_to_seconds(match[1])
                end_time = self._srt_time_to_seconds(match[2])
                timestamps.append({
                    "start_time": start_time,
                    "end_time": end_time,
                })

        except Exception as e:
            logger.warning(f"解析 SRT 文件失败: {e}")

        return timestamps

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

    async def _extract_frames_at_timestamps(
        self,
        video: Video,
        timestamps: List[Dict[str, float]],
        margin: float,
        fps: float,
        quality: int,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """在字幕时间点提取帧

        对每个字幕时间点，在其前后扩展margin范围内提取帧
        """
        frames_data = []
        frame_dir = os.path.join(settings.DOWNLOAD_DIR, "frames", video.id)
        os.makedirs(frame_dir, exist_ok=True)

        # 合并重叠的时间段
        merged_ranges = self._merge_time_ranges(timestamps, margin)
        logger.info(f"合并后的时间范围: {len(merged_ranges)} 个")

        for i, time_range in enumerate(merged_ranges):
            start_time = max(0, time_range["start"] - margin)
            end_time = time_range["end"] + margin

            # 计算需要提取的帧数
            duration = end_time - start_time
            num_frames = max(1, int(duration * fps))

            # 使用 ffmpeg 提取指定时间范围的帧
            output_pattern = os.path.join(frame_dir, f"subtitle_frame_{i}_%06d.jpg")

            cmd = [
                "ffmpeg",
                "-i", video.file_path,
                "-ss", str(start_time),
                "-t", str(duration),
                "-vf", f"fps={fps}",
                "-q:v", str(quality),
                "-y",
                output_pattern,
            ]

            await asyncio.to_thread(self._run_ffmpeg, cmd)

            # 获取提取的帧文件
            frame_files = sorted([
                f for f in os.listdir(frame_dir)
                if f.startswith(f"subtitle_frame_{i}_") and f.endswith(".jpg")
            ])

            # 计算时间戳
            for j, frame_file in enumerate(frame_files):
                frame_time = start_time + (j / fps)
                image_path = os.path.join(frame_dir, frame_file)

                # 验证帧是否有效
                if os.path.exists(image_path):
                    file_size = os.path.getsize(image_path)
                    quality_score = min(file_size / 100000, 1.0)

                    frames_data.append({
                        "timestamp": frame_time,
                        "frame_number": None,
                        "image_path": image_path,
                        "has_subtitle": True,  # 基于字幕时间点提取，默认标记为有字幕
                        "quality_score": quality_score,
                    })

            if progress_callback:
                progress_callback({
                    "current": i + 1,
                    "total": len(merged_ranges),
                    "percent": round((i + 1) / len(merged_ranges) * 100, 2),
                    "phase": "extracting_subtitle_frames",
                })

        return frames_data

    def _merge_time_ranges(
        self,
        timestamps: List[Dict[str, float]],
        gap_threshold: float = 1.0,
    ) -> List[Dict[str, float]]:
        """合并相近的时间范围

        Args:
            timestamps: 字幕时间戳列表
            gap_threshold: 时间间隔阈值（秒），小于此值则合并

        Returns:
            合并后的时间范围列表
        """
        if not timestamps:
            return []

        # 按开始时间排序
        sorted_ranges = sorted(timestamps, key=lambda x: x["start_time"])

        merged = []
        current = {
            "start": sorted_ranges[0]["start_time"],
            "end": sorted_ranges[0]["end_time"],
        }

        for i in range(1, len(sorted_ranges)):
            next_range = sorted_ranges[i]

            # 如果下一个范围与当前范围重叠或接近，则合并
            if next_range["start_time"] - current["end"] <= gap_threshold:
                current["end"] = max(current["end"], next_range["end_time"])
            else:
                merged.append(current)
                current = {
                    "start": next_range["start_time"],
                    "end": next_range["end_time"],
                }

        merged.append(current)
        return merged

    async def _extract_frames_with_subtitle_detection(
        self,
        video: Video,
        fps: float,
        quality: int,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """使用图像处理检测字幕区域并提取帧

        方法：
        1. 提取全量帧
        2. 使用图像处理检测帧底部区域是否有字幕
        3. 过滤掉不包含字幕的帧
        """
        frames_data = []
        frame_dir = os.path.join(settings.DOWNLOAD_DIR, "frames", video.id)
        os.makedirs(frame_dir, exist_ok=True)

        # 提取全量帧
        output_pattern = os.path.join(frame_dir, "detection_frame_%06d.jpg")

        cmd = [
            "ffmpeg",
            "-i", video.file_path,
            "-vf", f"fps={fps}",
            "-q:v", str(quality),
            "-y",
            output_pattern,
        ]

        await asyncio.to_thread(self._run_ffmpeg, cmd)

        # 获取提取的帧文件
        frame_files = sorted([
            f for f in os.listdir(frame_dir)
            if f.startswith("detection_frame_") and f.endswith(".jpg")
        ])

        # 获取视频时长
        video_duration = video.duration or await self._get_video_duration(video.file_path)

        # 检测每帧是否包含字幕
        for i, frame_file in enumerate(frame_files):
            frame_time = i / fps

            # 跳过视频末尾附近可能无效的帧
            if frame_time > video_duration:
                continue

            image_path = os.path.join(frame_dir, frame_file)

            if not os.path.exists(image_path):
                continue

            # 使用图像处理检测字幕区域
            has_subtitle = await self._detect_subtitle_by_image_processing(image_path)

            if has_subtitle:
                file_size = os.path.getsize(image_path)
                quality_score = min(file_size / 100000, 1.0)

                frames_data.append({
                    "timestamp": frame_time,
                    "frame_number": i + 1,
                    "image_path": image_path,
                    "has_subtitle": True,
                    "quality_score": quality_score,
                })

            if progress_callback:
                progress_callback({
                    "current": i + 1,
                    "total": len(frame_files),
                    "percent": round((i + 1) / len(frame_files) * 100, 2),
                    "phase": "detecting_subtitles",
                })

        return frames_data

    async def _detect_subtitle_by_image_processing(self, frame_path: str) -> bool:
        """使用图像处理方法检测帧是否包含字幕

        检测策略：
        1. 分析帧底部1/4区域（字幕通常在这里）
        2. 检测该区域是否有大量文字特征（边缘密度、对比度等）

        Returns:
            是否可能包含字幕
        """
        try:
            import numpy as np
            import cv2

            # 读取图像
            img = cv2.imread(frame_path)
            if img is None:
                return False

            height, width = img.shape[:2]

            # 提取底部1/4区域
            subtitle_region = img[int(height * 3 / 4):, :]

            # 转换为灰度图
            gray = cv2.cvtColor(subtitle_region, cv2.COLOR_BGR2GRAY)

            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)

            # 计算边缘密度
            edge_density = np.sum(edges > 0) / edges.size

            # 字幕区域通常有较高的边缘密度（文字边缘）
            # 设置阈值为 0.05，可以根据实际情况调整
            if edge_density > 0.05:
                return True

            # 额外检查：文字区域通常有均匀的对比度分布
            # 计算水平方向的梯度（文字通常是水平排列的）
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            horizontal_gradient = np.mean(np.abs(sobelx))

            # 如果水平梯度较大，可能包含字幕
            if horizontal_gradient > 20:
                return True

            return False

        except ImportError:
            logger.warning("OpenCV 未安装，使用占位检测")
            return True
        except Exception as e:
            logger.warning(f"图像处理检测失败: {e}")
            return True  # 无法判断时保守返回 True

    async def delete_frames_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有帧记录和文件"""
        frames = await self.get_frames_by_video(db, video_id)

        # 删除帧文件
        frame_dir = os.path.join(settings.DOWNLOAD_DIR, "frames", video_id)
        if os.path.exists(frame_dir):
            for frame in frames:
                if frame.image_path and os.path.exists(frame.image_path):
                    try:
                        os.remove(frame.image_path)
                    except Exception:
                        pass
            # 尝试删除目录
            try:
                os.rmdir(frame_dir)
            except Exception:
                pass

        # 删除数据库记录
        count = 0
        for frame in frames:
            await db.delete(frame)
            count += 1
        await db.commit()

        return count


# 单例实例
frame_service = FrameService()