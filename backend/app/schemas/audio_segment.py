"""音频片段数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AudioSegmentBase(BaseModel):
    start_time: float
    end_time: float
    asr_text: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None


class AudioSegmentCreate(AudioSegmentBase):
    video_id: str
    audio_path: Optional[str] = None


class AudioSegmentUpdate(BaseModel):
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    asr_text: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None
    audio_path: Optional[str] = None


class AudioSegmentResponse(AudioSegmentBase):
    id: str
    video_id: str
    audio_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AudioExtractionConfig(BaseModel):
    """音频提取配置"""
    format: str = "wav"  # wav, mp3, flac
    sample_rate: int = 16000  # 采样率
    channels: int = 1  # 声道数
    bitrate: Optional[str] = None  # 比特率


class ASRConfig(BaseModel):
    """ASR 配置"""
    model: str = "whisper"  # whisper, google, azure
    language: Optional[str] = None  # 自动检测
    task: str = "transcribe"  # transcribe, translate