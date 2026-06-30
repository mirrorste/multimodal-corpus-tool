import asyncio
import os
import shutil
import time
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile
import aiofiles

from app.models.video import Video
from app.services.video_downloader import downloader
from app.core.config import settings


class VideoService:
    def __init__(self):
        os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        self._download_semaphore = asyncio.Semaphore(3)
        self._progress_throttle = {}

    async def get_video(self, db: AsyncSession, video_id: str) -> Optional[Video]:
        result = await db.execute(select(Video).where(Video.id == video_id))
        return result.scalar_one_or_none()

    async def create_video(
        self,
        db: AsyncSession,
        url: str,
        platform: str,
        preferred_resolution: str = "1080p",
        fetch_info: bool = True,
    ) -> Video:
        video = Video(
            url=url,
            platform=platform,
            preferred_resolution=preferred_resolution,
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)
        return video

    def fetch_and_update_video_info_sync(self, video_id: str, url: str):
        from app.core.database import async_session_maker
        import asyncio as _asyncio
        try:
            info = downloader.get_video_info(url)
            if info:
                async def _update():
                    async with async_session_maker() as session:
                        video = await self.get_video(session, video_id)
                        if video and not video.title:
                            video.title = info.get("title")
                            video.duration = info.get("duration")
                            video.thumbnail = info.get("thumbnail")
                            await session.commit()
                _asyncio.run(_update())
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning(f"获取视频信息失败: {e}")

    async def update_video_status(
        self,
        db: AsyncSession,
        video_id: str,
        status: str,
        **kwargs,
    ) -> Optional[Video]:
        video = await self.get_video(db, video_id)
        if not video:
            return None
        video.status = status
        for key, value in kwargs.items():
            if value is not None and hasattr(video, key):
                setattr(video, key, value)
        await db.commit()
        await db.refresh(video)
        return video

    def _run_sync_download(
        self,
        url: str,
        resolution: str,
        video_id: str,
    ) -> Dict[str, Any]:
        progress_history = []

        def progress_callback(progress_data):
            progress_history.append(progress_data)
            asyncio.run(self._update_progress_async(video_id, progress_data))

        result = downloader.download_video(
            url=url,
            resolution=resolution,
            progress_callback=progress_callback,
        )
        return result

    async def _update_progress_async(
        self,
        video_id: str,
        progress_data: Dict[str, Any],
    ):
        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            video = await self.get_video(session, video_id)
            if not video:
                return
            downloaded = progress_data.get("downloaded_bytes", 0)
            total = progress_data.get("total_bytes", 0)
            if total > 0:
                video.download_progress = round((downloaded / total) * 100, 2)
            video.downloaded_bytes = downloaded
            video.total_bytes = total
            if progress_data.get("status") == "downloading":
                if video.status != "downloading":
                    video.status = "downloading"
            await session.commit()

    async def start_download(
        self,
        db: AsyncSession,
        video_id: str,
    ) -> Optional[Video]:
        video = await self.get_video(db, video_id)
        if not video:
            return None

        if video.status in ("downloading", "processing", "completed"):
            return video

        video.status = "queued"
        video.download_progress = 0.0
        video.downloaded_bytes = 0.0
        video.total_bytes = 0.0
        video.error_message = None
        await db.commit()
        await db.refresh(video)

        asyncio.create_task(self._download_task(video_id))

        return video

    async def _download_task(self, video_id: str):
        from app.core.database import async_session_maker
        async with self._download_semaphore:
            async with async_session_maker() as session:
                video = await self.get_video(session, video_id)
                if not video:
                    return

                try:
                    video.status = "downloading"
                    await session.commit()

                    result = await asyncio.to_thread(
                        self._sync_download_with_progress,
                        video_id,
                        video.url,
                        video.preferred_resolution or "1080p",
                    )

                    await session.refresh(video)
                    if result.get("success"):
                        video.status = "completed"
                        video.title = result.get("title")
                        video.duration = result.get("duration")
                        video.resolution = result.get("resolution")
                        video.file_path = result.get("file_path")
                        if result.get("file_size"):
                            video.file_size = result["file_size"]
                            video.total_bytes = result["file_size"]
                            video.downloaded_bytes = result["file_size"]
                        video.download_progress = 100.0
                    else:
                        video.status = "failed"
                        video.error_message = result.get("error", "下载失败")

                    await session.commit()

                except Exception as e:
                    await session.refresh(video)
                    video.status = "failed"
                    video.error_message = f"下载异常: {str(e)}"
                    await session.commit()
                finally:
                    self._progress_throttle.pop(video_id, None)

    def _sync_download_with_progress(
        self,
        video_id: str,
        url: str,
        resolution: str,
    ) -> Dict[str, Any]:
        def progress_callback(progress_data):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    self._update_progress_sync(video_id, progress_data)
                )
            finally:
                loop.close()

        result = downloader.download_video(
            url=url,
            resolution=resolution,
            progress_callback=progress_callback,
        )
        return result

    async def _update_progress_sync(
        self,
        video_id: str,
        progress_data: Dict[str, Any],
    ):
        now = time.time()
        last_update = self._progress_throttle.get(video_id, 0)
        if now - last_update < 1.0:
            return
        self._progress_throttle[video_id] = now

        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(
                select(Video).where(Video.id == video_id)
            )
            video = result.scalar_one_or_none()
            if not video:
                return
            downloaded = progress_data.get("downloaded_bytes", 0)
            total = progress_data.get("total_bytes", 0)
            if total > 0:
                video.download_progress = round((downloaded / total) * 100, 2)
            video.downloaded_bytes = downloaded
            video.total_bytes = total
            status = progress_data.get("status")
            if status == "downloading" and video.status == "queued":
                video.status = "downloading"
            await session.commit()

    async def upload_local_video(
        self,
        db: AsyncSession,
        file: UploadFile,
        platform: str = "local",
        preferred_resolution: str = "original",
    ) -> Video:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
        import uuid
        safe_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

        file_size = 0
        async with aiofiles.open(file_path, "wb") as out_file:
            while content := await file.read(1024 * 1024):
                file_size += len(content)
                if file_size > settings.MAX_UPLOAD_SIZE * 1024 * 1024:
                    await out_file.close()
                    os.remove(file_path)
                    raise ValueError(
                        f"文件大小超过限制（最大 {settings.MAX_UPLOAD_SIZE}MB）"
                    )
                await out_file.write(content)

        video = Video(
            url=file_path,
            platform=platform,
            title=file.filename or safe_filename,
            status="completed",
            file_path=file_path,
            file_size=file_size,
            preferred_resolution=preferred_resolution,
            download_progress=100.0,
            downloaded_bytes=file_size,
            total_bytes=file_size,
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)
        return video

    async def delete_video_files(self, video: Video):
        if video.file_path and os.path.exists(video.file_path):
            try:
                os.remove(video.file_path)
            except Exception:
                pass

    async def batch_start_download(self, db: AsyncSession, video_ids: list[str]) -> dict:
        results = {"success": [], "failed": [], "skipped": []}
        for vid in video_ids:
            try:
                video = await self.get_video(db, vid)
                if not video:
                    results["failed"].append({"id": vid, "reason": "视频不存在"})
                    continue
                if video.status in ("downloading", "processing", "completed", "queued"):
                    results["skipped"].append({"id": vid, "status": video.status, "reason": "当前状态无需重新下载"})
                    continue
                video = await self.start_download(db, vid)
                if video:
                    results["success"].append({"id": vid, "status": video.status})
                else:
                    results["failed"].append({"id": vid, "reason": "启动失败"})
            except Exception as e:
                results["failed"].append({"id": vid, "reason": str(e)})
        return results

    async def batch_cancel(self, db: AsyncSession, video_ids: list[str]) -> dict:
        results = {"success": [], "failed": [], "skipped": []}
        for vid in video_ids:
            try:
                video = await self.get_video(db, vid)
                if not video:
                    results["failed"].append({"id": vid, "reason": "视频不存在"})
                    continue
                if video.status in ("completed", "failed", "cancelled"):
                    results["skipped"].append({"id": vid, "status": video.status, "reason": "当前状态无需取消"})
                    continue
                video = await self.update_video_status(
                    db, vid, "cancelled",
                    error_message="用户批量取消任务",
                )
                if video:
                    results["success"].append({"id": vid, "status": "cancelled"})
                else:
                    results["failed"].append({"id": vid, "reason": "取消失败"})
            except Exception as e:
                results["failed"].append({"id": vid, "reason": str(e)})
        return results

    async def batch_delete(self, db: AsyncSession, video_ids: list[str]) -> dict:
        results = {"success": [], "failed": []}
        for vid in video_ids:
            try:
                video = await self.get_video(db, vid)
                if not video:
                    results["failed"].append({"id": vid, "reason": "视频不存在"})
                    continue
                await self.delete_video_files(video)
                await db.delete(video)
                await db.commit()
                results["success"].append({"id": vid})
            except Exception as e:
                results["failed"].append({"id": vid, "reason": str(e)})
        return results


video_service = VideoService()
