from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from app.schemas.video import VideoCreate, VideoResponse
from app.services.video_service import video_service
from app.services.video_downloader import downloader
from sqlalchemy import select
from typing import Optional

router = APIRouter()


@router.post("/", response_model=VideoResponse)
async def create_video(
    video_in: VideoCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    video = await video_service.create_video(
        db=db,
        url=video_in.url,
        platform=video_in.platform,
        preferred_resolution=video_in.preferred_resolution,
    )
    background_tasks.add_task(
        video_service.fetch_and_update_video_info_sync,
        video.id,
        video.url,
    )
    return video


@router.get("/", response_model=list[VideoResponse])
async def get_videos(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Video)
    if status:
        query = query.where(Video.status == status)
    if platform:
        query = query.where(Video.platform == platform)
    query = query.order_by(Video.created_at.desc())
    result = await db.execute(query)
    videos = result.scalars().all()
    return videos


@router.post("/upload", response_model=VideoResponse)
async def upload_video(
    file: UploadFile = File(...),
    platform: str = Form("local"),
    preferred_resolution: str = Form("original"),
    db: AsyncSession = Depends(get_db),
):
    allowed_extensions = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v"}
    file_ext = ""
    if file.filename:
        file_ext = file.filename.lower()
        for ext in allowed_extensions:
            if file_ext.endswith(ext):
                file_ext = ext
                break
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式。支持的格式: {', '.join(allowed_extensions)}",
            )
    try:
        video = await video_service.upload_local_video(
            db=db,
            file=file,
            platform=platform,
            preferred_resolution=preferred_resolution,
        )
        return video
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/batch", response_model=list[VideoResponse])
async def create_videos_batch(
    videos_in: list[VideoCreate],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    videos = []
    for video_in in videos_in:
        video = await video_service.create_video(
            db=db,
            url=video_in.url,
            platform=video_in.platform,
            preferred_resolution=video_in.preferred_resolution,
        )
        background_tasks.add_task(
            video_service.fetch_and_update_video_info_sync,
            video.id,
            video.url,
        )
        videos.append(video)
    return videos


@router.post("/batch/download")
async def batch_download_videos(video_ids: list[str] = Body(...), db: AsyncSession = Depends(get_db)):
    if not video_ids:
        raise HTTPException(status_code=400, detail="请选择要下载的视频")
    result = await video_service.batch_start_download(db, video_ids)
    return {
        "message": f"批量下载操作完成：成功 {len(result['success'])} 个，跳过 {len(result['skipped'])} 个，失败 {len(result['failed'])} 个",
        **result,
    }


@router.post("/batch/cancel")
async def batch_cancel_videos(video_ids: list[str] = Body(...), db: AsyncSession = Depends(get_db)):
    if not video_ids:
        raise HTTPException(status_code=400, detail="请选择要取消的视频")
    result = await video_service.batch_cancel(db, video_ids)
    return {
        "message": f"批量取消操作完成：成功 {len(result['success'])} 个，跳过 {len(result['skipped'])} 个，失败 {len(result['failed'])} 个",
        **result,
    }


@router.delete("/batch")
async def batch_delete_videos(video_ids: list[str] = Body(...), db: AsyncSession = Depends(get_db)):
    if not video_ids:
        raise HTTPException(status_code=400, detail="请选择要删除的视频")
    result = await video_service.batch_delete(db, video_ids)
    return {
        "message": f"批量删除操作完成：成功 {len(result['success'])} 个，失败 {len(result['failed'])} 个",
        **result,
    }


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    await video_service.delete_video_files(video)
    await db.delete(video)
    await db.commit()
    return {"message": "视频删除成功"}


@router.post("/{video_id}/download", response_model=VideoResponse)
async def start_download(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.start_download(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.get("/{video_id}/progress")
async def get_download_progress(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return {
        "video_id": video.id,
        "status": video.status,
        "download_progress": video.download_progress,
        "downloaded_bytes": video.downloaded_bytes,
        "total_bytes": video.total_bytes,
        "error_message": video.error_message,
        "updated_at": video.updated_at,
    }


@router.get("/{video_id}/info")
async def fetch_video_info(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    try:
        info = downloader.get_video_info(video.url)
        return {
            "video_id": video.id,
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取视频信息失败: {str(e)}")
