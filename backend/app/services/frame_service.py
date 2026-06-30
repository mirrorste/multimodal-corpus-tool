"""帧提取服务"""
import asyncio
import os
import subprocess
from typing import Optional, Callable, Dict, Any
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