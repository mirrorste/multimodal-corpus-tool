from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from app.services.video_service import video_service
from sqlalchemy import select

router = APIRouter()


@router.get("/{task_id}")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.get_video(db, task_id)
    if not video:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": video.id,
        "status": video.status,
        "title": video.title,
        "download_progress": video.download_progress,
        "downloaded_bytes": video.downloaded_bytes,
        "total_bytes": video.total_bytes,
        "error_message": video.error_message,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
    }


@router.post("/{task_id}/process")
async def process_task(task_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.start_download(db, task_id)
    if not video:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "message": "任务开始处理",
        "task_id": task_id,
        "status": video.status,
    }


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    video = await video_service.get_video(db, task_id)
    if not video:
        raise HTTPException(status_code=404, detail="任务不存在")
    if video.status in ("completed", "failed", "cancelled"):
        return {
            "message": f"任务当前状态为 {video.status}，无需取消",
            "task_id": task_id,
            "status": video.status,
        }
    video = await video_service.update_video_status(
        db, task_id, "cancelled",
        error_message="用户取消任务",
    )
    return {
        "message": "任务已取消",
        "task_id": task_id,
        "status": video.status if video else "cancelled",
    }


@router.get("/")
async def list_tasks(
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Video)
    if status:
        query = query.where(Video.status == status)
    query = query.order_by(Video.created_at.desc())
    result = await db.execute(query)
    videos = result.scalars().all()
    return [
        {
            "task_id": v.id,
            "status": v.status,
            "title": v.title,
            "download_progress": v.download_progress,
            "platform": v.platform,
            "created_at": v.created_at,
            "updated_at": v.updated_at,
        }
        for v in videos
    ]
