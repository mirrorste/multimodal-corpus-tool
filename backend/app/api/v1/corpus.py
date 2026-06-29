from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from sqlalchemy import select

router = APIRouter()


@router.get("/{video_id}")
async def get_corpus(video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return {
        "video_info": {
            "id": video.id,
            "url": video.url,
            "title": video.title,
            "duration": video.duration,
            "resolution": video.resolution,
        },
        "timeline": [],
    }


@router.get("/{video_id}/export")
async def export_corpus(video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return {"message": "导出功能开发中", "video_id": video_id}


@router.get("/annotations")
async def get_annotations(db: AsyncSession = Depends(get_db)):
    return {"message": "标注数据查询功能开发中"}
