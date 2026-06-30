from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from app.schemas.video import VideoCreate, VideoResponse
from app.schemas.frame import FrameResponse
from app.schemas.subtitle import SubtitleResponse, SubtitleUpdate
from app.schemas.audio_segment import AudioSegmentResponse, AudioSegmentUpdate
from app.schemas.visual_description import VisualDescriptionResponse, VisualDescriptionUpdate
from app.services.video_service import video_service
from app.services.video_downloader import downloader
from app.services.frame_service import frame_service
from app.services.subtitle_service import subtitle_service
from app.services.audio_service import audio_service
from app.services.visual_service import visual_service
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


@router.post("/{video_id}/frames/extract-subtitle")
async def extract_subtitle_frames(
    video_id: str,
    fps: float = Query(default=1.0, ge=0.1, le=10.0, description="每秒提取帧数"),
    quality: int = Query(default=2, ge=1, le=5, description="图片质量 1-5，越小质量越高"),
    margin: float = Query(default=0.5, ge=0.0, le=5.0, description="字幕时间戳前后扩展边距（秒）"),
    db: AsyncSession = Depends(get_db),
):
    """提取包含字幕的画面帧

    策略：
    1. 优先检测内嵌字幕轨道，使用字幕时间戳提取帧
    2. 如果没有内嵌字幕，使用图像处理检测字幕区域

    - **fps**: 每秒提取帧数，默认 1.0
    - **quality**: 图片质量 1-5，默认 2（质量较高）
    - **margin**: 字幕时间戳前后扩展边距，默认 0.5 秒
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if video.status != "completed":
        raise HTTPException(status_code=400, detail=f"视频状态为 {video.status}，请先完成下载")

    result = await frame_service.extract_subtitle_frames(
        db=db,
        video_id=video_id,
        fps=fps,
        quality=quality,
        margin=margin,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "提取失败"))

    return {
        "message": "字幕帧提取完成",
        "video_id": video_id,
        "total_frames": result["total_frames"],
        "has_embedded_subtitles": result["has_embedded_subtitles"],
        "frame_ids": result["subtitle_frames"],
    }


@router.get("/{video_id}/frames", response_model=list[FrameResponse])
async def get_video_frames(
    video_id: str,
    start_time: Optional[float] = Query(default=None, description="起始时间（秒）"),
    end_time: Optional[float] = Query(default=None, description="结束时间（秒）"),
    has_subtitle: Optional[bool] = Query(default=None, description="是否包含字幕"),
    db: AsyncSession = Depends(get_db),
):
    """获取视频的所有帧列表

    - **start_time**: 筛选起始时间（秒）
    - **end_time**: 筛选结束时间（秒）
    - **has_subtitle**: 筛选包含字幕的帧
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    frames = await frame_service.get_frames_by_video(
        db=db,
        video_id=video_id,
        start_time=start_time,
        end_time=end_time,
    )

    # 如果指定了 has_subtitle 过滤
    if has_subtitle is not None:
        frames = [f for f in frames if f.has_subtitle == has_subtitle]

    return frames


@router.get("/{video_id}/frames/{frame_id}", response_model=FrameResponse)
async def get_frame(
    video_id: str,
    frame_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单帧详情"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    frame = await frame_service.get_frame(db, frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="帧不存在")

    if frame.video_id != video_id:
        raise HTTPException(status_code=404, detail="帧不属于该视频")

    return frame


@router.post("/{video_id}/frames/detect-subtitles")
async def detect_subtitle_frames(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """检测已提取帧中包含字幕的帧

    对已提取的帧进行字幕检测，更新 has_subtitle 字段
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    result = await frame_service.detect_subtitle_frames(db, video_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "检测失败"))

    return {
        "message": "字幕帧检测完成",
        "video_id": video_id,
        "total_frames": result["total_frames"],
        "subtitle_frames": result["subtitle_frames"],
    }


@router.delete("/{video_id}/frames")
async def delete_video_frames(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除视频的所有帧记录和文件"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    count = await frame_service.delete_frames_by_video(db, video_id)

    return {
        "message": f"删除帧记录 {count} 条",
        "video_id": video_id,
        "deleted_count": count,
    }


# ==================== 字幕相关接口 ====================

@router.post("/{video_id}/subtitles/extract")
async def extract_subtitles(
    video_id: str,
    source: str = Query(default="auto", description="字幕来源: auto/embedded/ocr/asr"),
    language: Optional[str] = Query(default=None, description="指定语言代码，如 zh/en/ja/ko"),
    db: AsyncSession = Depends(get_db),
):
    """触发字幕提取

    - **source**: 字幕来源
        - auto: 自动选择（内嵌 > OCR > ASR）
        - embedded: 仅内嵌字幕轨道
        - ocr: 仅 OCR 硬字幕
        - asr: 仅 ASR 语音识别
    - **language**: 期望语言代码（可选）
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status != "completed":
        raise HTTPException(status_code=400, detail=f"视频状态为 {video.status}，请先完成下载")

    if source not in ("auto", "embedded", "ocr", "asr"):
        raise HTTPException(status_code=400, detail=f"不支持的 source: {source}")

    result = await subtitle_service.extract_subtitles(
        db=db,
        video_id=video_id,
        source=source,
        language=language,
    )

    if not result["success"]:
        # auto 模式下若全部失败，使用 200 返回失败信息（前端可选择重试）
        if source == "auto":
            return {
                "success": False,
                "message": result.get("error", "字幕提取失败"),
                "video_id": video_id,
                "total_subtitles": 0,
            }
        raise HTTPException(status_code=400, detail=result.get("error", "提取失败"))

    return {
        "success": True,
        "message": f"字幕提取完成（来源: {result.get('source_used') or source}）",
        "video_id": video_id,
        "source_used": result.get("source_used") or source,
        "total_subtitles": result["total_subtitles"],
        "subtitle_ids": result["subtitles"],
    }


@router.get("/{video_id}/subtitles", response_model=list[SubtitleResponse])
async def get_video_subtitles(
    video_id: str,
    start_time: Optional[float] = Query(default=None, description="起始时间（秒）"),
    end_time: Optional[float] = Query(default=None, description="结束时间（秒）"),
    language: Optional[str] = Query(default=None, description="按语言筛选"),
    source: Optional[str] = Query(default=None, description="按来源筛选 embedded/OCR/asr"),
    db: AsyncSession = Depends(get_db),
):
    """获取视频的所有字幕列表

    - **start_time**: 筛选起始时间
    - **end_time**: 筛选结束时间
    - **language**: 按语言筛选
    - **source**: 按来源筛选
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    subtitles = await subtitle_service.get_subtitles_by_video(
        db=db,
        video_id=video_id,
        start_time=start_time,
        end_time=end_time,
        language=language,
        source=source,
    )
    return subtitles


@router.get("/{video_id}/subtitles/{subtitle_id}", response_model=SubtitleResponse)
async def get_subtitle(
    video_id: str,
    subtitle_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单条字幕详情"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    subtitle = await subtitle_service.get_subtitle(db, subtitle_id)
    if not subtitle:
        raise HTTPException(status_code=404, detail="字幕不存在")

    if subtitle.video_id != video_id:
        raise HTTPException(status_code=404, detail="字幕不属于该视频")

    return subtitle


@router.put("/{video_id}/subtitles/{subtitle_id}", response_model=SubtitleResponse)
async def update_subtitle(
    video_id: str,
    subtitle_id: str,
    update_data: SubtitleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新字幕（人工校正）

    支持修改文本、时间轴、语言、来源
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    subtitle = await subtitle_service.get_subtitle(db, subtitle_id)
    if not subtitle:
        raise HTTPException(status_code=404, detail="字幕不存在")
    if subtitle.video_id != video_id:
        raise HTTPException(status_code=404, detail="字幕不属于该视频")

    updated = await subtitle_service.update_subtitle(
        db=db,
        subtitle_id=subtitle_id,
        text=update_data.text,
        start_time=update_data.start_time,
        end_time=update_data.end_time,
        language=update_data.language,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="更新失败")

    return updated


@router.delete("/{video_id}/subtitles")
async def delete_video_subtitles(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除视频的所有字幕记录"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    count = await subtitle_service.delete_subtitles_by_video(db, video_id)

    return {
        "message": f"删除字幕记录 {count} 条",
        "video_id": video_id,
        "deleted_count": count,
    }


# ==================== 音频相关接口 ====================

@router.post("/{video_id}/audio/extract")
async def extract_audio(
    video_id: str,
    format: str = Query(default="wav", description="音频格式: wav/mp3/flac"),
    denoise: bool = Query(default=False, description="是否降噪处理"),
    db: AsyncSession = Depends(get_db),
):
    """从视频提取完整音频

    - **format**: 音频格式，默认 wav
    - **denoise**: 是否启用降噪处理
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status != "completed":
        raise HTTPException(status_code=400, detail=f"视频状态为 {video.status}，请先完成下载")

    result = await audio_service.extract_audio(
        db=db,
        video_id=video_id,
        format=format,
        denoise=denoise,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "音频提取失败"))

    return {
        "success": True,
        "message": "音频提取完成",
        "video_id": video_id,
        "audio_path": result["audio_path"],
        "duration": result["duration"],
        "segment_id": result["segment_id"],
    }


@router.post("/{video_id}/audio/extract-segments")
async def extract_audio_segments(
    video_id: str,
    time_segments: list[dict] = Body(..., description="时间段列表: [{'start': 0.0, 'end': 10.0}, ...]"),
    format: str = Query(default="wav", description="音频格式: wav/mp3/flac"),
    denoise: bool = Query(default=False, description="是否降噪处理"),
    db: AsyncSession = Depends(get_db),
):
    """按时间段提取音频片段

    - **time_segments**: 时间段列表，如 [{"start": 0.0, "end": 10.0}, {"start": 10.0, "end": 20.0}]
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status != "completed":
        raise HTTPException(status_code=400, detail=f"视频状态为 {video.status}，请先完成下载")

    result = await audio_service.extract_audio_segments(
        db=db,
        video_id=video_id,
        time_segments=time_segments,
        format=format,
        denoise=denoise,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "音频片段提取失败"))

    return {
        "success": True,
        "message": f"音频片段提取完成: {result['total_segments']} 个",
        "video_id": video_id,
        "total_segments": result["total_segments"],
        "segment_ids": result["segments"],
    }


@router.post("/{video_id}/audio/extract-by-subtitles")
async def extract_audio_by_subtitles(
    video_id: str,
    format: str = Query(default="wav", description="音频格式: wav/mp3/flac"),
    denoise: bool = Query(default=False, description="是否降噪处理"),
    db: AsyncSession = Depends(get_db),
):
    """按字幕时间戳提取音频片段

    根据已提取的字幕时间轴，提取每个字幕对应时间段的音频
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status != "completed":
        raise HTTPException(status_code=400, detail=f"视频状态为 {video.status}，请先完成下载")

    result = await audio_service.extract_audio_by_subtitles(
        db=db,
        video_id=video_id,
        format=format,
        denoise=denoise,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "音频提取失败"))

    return {
        "success": True,
        "message": f"按字幕提取音频片段完成: {result['total_segments']} 个",
        "video_id": video_id,
        "total_segments": result["total_segments"],
        "segment_ids": result["segments"],
    }


@router.post("/{video_id}/audio/asr")
async def perform_audio_asr(
    video_id: str,
    language: Optional[str] = Query(default=None, description="指定语言代码，如 zh/en/ja/ko"),
    denoise: bool = Query(default=False, description="是否降噪处理"),
    db: AsyncSession = Depends(get_db),
):
    """对视频音频进行 ASR 语音识别

    使用 ASRProvider 进行语音识别，支持本地 Whisper 和云端 API 自动降级
    - **language**: 指定语言（可选，不指定则自动检测）
    - **denoise**: 是否启用降噪处理
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status != "completed":
        raise HTTPException(status_code=400, detail=f"视频状态为 {video.status}，请先完成下载")

    result = await audio_service.perform_asr(
        db=db,
        video_id=video_id,
        language=language,
        denoise=denoise,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "ASR 识别失败"))

    return {
        "success": True,
        "message": f"ASR 识别完成: {result['total_segments']} 个片段",
        "video_id": video_id,
        "detected_language": result.get("detected_language"),
        "provider": result.get("provider"),
        "total_segments": result["total_segments"],
        "segment_ids": result["segments"],
    }


@router.get("/{video_id}/audio", response_model=list[AudioSegmentResponse])
async def get_audio_segments(
    video_id: str,
    start_time: Optional[float] = Query(default=None, description="起始时间（秒）"),
    end_time: Optional[float] = Query(default=None, description="结束时间（秒）"),
    has_asr: Optional[bool] = Query(default=None, description="是否包含 ASR 文本"),
    db: AsyncSession = Depends(get_db),
):
    """获取视频的所有音频片段列表

    - **start_time**: 筛选起始时间
    - **end_time**: 筛选结束时间
    - **has_asr**: 筛选包含 ASR 文本的片段
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    segments = await audio_service.get_audio_segments_by_video(
        db=db,
        video_id=video_id,
        start_time=start_time,
        end_time=end_time,
        has_asr=has_asr,
    )
    return segments


@router.get("/{video_id}/audio/{segment_id}", response_model=AudioSegmentResponse)
async def get_audio_segment(
    video_id: str,
    segment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单个音频片段详情"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    segment = await audio_service.get_audio_segment(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="音频片段不存在")

    if segment.video_id != video_id:
        raise HTTPException(status_code=404, detail="音频片段不属于该视频")

    return segment


@router.put("/{video_id}/audio/{segment_id}", response_model=AudioSegmentResponse)
async def update_audio_segment(
    video_id: str,
    segment_id: str,
    update_data: AudioSegmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新音频片段（人工校正 ASR 结果）"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    segment = await audio_service.get_audio_segment(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="音频片段不存在")
    if segment.video_id != video_id:
        raise HTTPException(status_code=404, detail="音频片段不属于该视频")

    updated = await audio_service.update_audio_segment(
        db=db,
        segment_id=segment_id,
        asr_text=update_data.asr_text,
        language=update_data.language,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="更新失败")

    return updated


@router.delete("/{video_id}/audio")
async def delete_audio_segments(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除视频的所有音频片段记录和文件"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    count = await audio_service.delete_audio_segments_by_video(db, video_id)

    return {
        "message": f"删除音频片段记录 {count} 条",
        "video_id": video_id,
        "deleted_count": count,
    }


# ==================== 视觉描述相关接口 ====================

@router.get("/visual/status")
async def get_visual_service_status():
    """获取视觉分析服务状态"""
    return visual_service.is_available()


@router.post("/{video_id}/visual/analyze")
async def analyze_video_frames(
    video_id: str,
    enable_description: bool = Query(default=True, description="生成图像描述"),
    enable_object_detection: bool = Query(default=True, description="物体检测"),
    enable_scene_classification: bool = Query(default=False, description="场景分类（需 LLM）"),
    enable_emotion_detection: bool = Query(default=False, description="情感分析（需 LLM）"),
    skip_existing: bool = Query(default=True, description="跳过已有描述的帧"),
    db: AsyncSession = Depends(get_db),
):
    """批量分析视频所有帧的视觉内容

    - **enable_description**: 图像描述（基于 VisionProvider）
    - **enable_object_detection**: 物体检测（基于 YOLO / 云端 API）
    - **enable_scene_classification**: 场景分类（基于 LLM）
    - **enable_emotion_detection**: 情感分析（基于 LLM）
    - **skip_existing**: 跳过已有描述的帧
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    result = await visual_service.analyze_video_frames(
        db=db,
        video_id=video_id,
        enable_description=enable_description,
        enable_object_detection=enable_object_detection,
        enable_scene_classification=enable_scene_classification,
        enable_emotion_detection=enable_emotion_detection,
        skip_existing=skip_existing,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "分析失败"))

    return {
        "success": True,
        "message": (
            f"视觉分析完成: 成功 {result['success_count']}, "
            f"失败 {result['failed_count']}, 跳过 {result['skipped_count']}"
        ),
        "video_id": video_id,
        "total_frames": result["total_frames"],
        "success_count": result["success_count"],
        "failed_count": result["failed_count"],
        "skipped_count": result["skipped_count"],
        "descriptions": result["descriptions"],
    }


@router.post("/visual/frames/{frame_id}/analyze")
async def analyze_single_frame(
    frame_id: str,
    enable_description: bool = Query(default=True, description="生成图像描述"),
    enable_object_detection: bool = Query(default=True, description="物体检测"),
    enable_scene_classification: bool = Query(default=False, description="场景分类"),
    enable_emotion_detection: bool = Query(default=False, description="情感分析"),
    db: AsyncSession = Depends(get_db),
):
    """分析单帧图像"""
    result = await visual_service.analyze_frame(
        db=db,
        frame_id=frame_id,
        enable_description=enable_description,
        enable_object_detection=enable_object_detection,
        enable_scene_classification=enable_scene_classification,
        enable_emotion_detection=enable_emotion_detection,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "分析失败"))

    return result


@router.get("/{video_id}/visual", response_model=list[VisualDescriptionResponse])
async def get_video_visual_descriptions(
    video_id: str,
    scene: Optional[str] = Query(default=None, description="按场景筛选"),
    limit: Optional[int] = Query(default=None, description="限制返回数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取视频的所有视觉描述记录

    - **scene**: 按场景名称筛选
    - **limit**: 限制返回记录数
    """
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    descriptions = await visual_service.get_visual_descriptions_by_video(
        db=db,
        video_id=video_id,
        scene=scene,
        limit=limit,
    )
    return descriptions


@router.get("/{video_id}/visual/{description_id}", response_model=VisualDescriptionResponse)
async def get_visual_description(
    video_id: str,
    description_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单条视觉描述详情"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    description = await visual_service.get_visual_description(db, description_id)
    if not description:
        raise HTTPException(status_code=404, detail="视觉描述不存在")

    # 验证所属视频
    from app.models.frame import Frame
    frame_result = await db.execute(select(Frame).where(Frame.id == description.frame_id))
    frame = frame_result.scalar_one_or_none()
    if not frame or frame.video_id != video_id:
        raise HTTPException(status_code=404, detail="视觉描述不属于该视频")

    return description


@router.put("/{video_id}/visual/{description_id}", response_model=VisualDescriptionResponse)
async def update_visual_description(
    video_id: str,
    description_id: str,
    update_data: VisualDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新视觉描述（人工校正）"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    description = await visual_service.get_visual_description(db, description_id)
    if not description:
        raise HTTPException(status_code=404, detail="视觉描述不存在")

    updated = await visual_service.update_visual_description(
        db=db,
        description_id=description_id,
        description=update_data.description,
        objects=update_data.objects,
        scene=update_data.scene,
        emotions=update_data.emotions,
        confidence=update_data.confidence,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="更新失败")

    return updated


@router.delete("/{video_id}/visual")
async def delete_visual_descriptions(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除视频的所有视觉描述记录"""
    video = await video_service.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    count = await visual_service.delete_visual_descriptions_by_video(db, video_id)

    return {
        "message": f"删除视觉描述记录 {count} 条",
        "video_id": video_id,
        "deleted_count": count,
    }
