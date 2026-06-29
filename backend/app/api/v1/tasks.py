from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from sqlalchemy import select

router = APIRouter()


@router.get("/{task_id}")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == task_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": video.id,
        "status": video.status,
        "title": video.title,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
    }


@router.post("/{task_id}/process")
async def process_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == task_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="任务不存在")
    video.status = "processing"
    await db.commit()
    await db.refresh(video)
    return {"message": "任务开始处理", "task_id": task_id, "status": video.status}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == task_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="任务不存在")
    video.status = "cancelled"
    await db.commit()
    await db.refresh(video)
    return {"message": "任务已取消", "task_id": task_id, "status": video.status}
