from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from app.schemas.video import VideoCreate, VideoResponse
from sqlalchemy import select

router = APIRouter()


@router.post("/", response_model=VideoResponse)
async def create_video(video_in: VideoCreate, db: AsyncSession = Depends(get_db)):
    video = Video(
        url=video_in.url,
        platform=video_in.platform,
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


@router.get("/", response_model=list[VideoResponse])
async def get_videos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video))
    videos = result.scalars().all()
    return videos


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    await db.delete(video)
    await db.commit()
    return {"message": "视频删除成功"}


@router.post("/batch")
async def create_videos_batch(videos_in: list[VideoCreate], db: AsyncSession = Depends(get_db)):
    videos = []
    for video_in in videos_in:
        video = Video(
            url=video_in.url,
            platform=video_in.platform,
        )
        db.add(video)
        videos.append(video)
    await db.commit()
    for video in videos:
        await db.refresh(video)
    return videos
