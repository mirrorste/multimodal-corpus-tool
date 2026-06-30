"""Services 模块导出"""
from app.services.video_service import video_service, VideoService
from app.services.video_downloader import downloader, VideoDownloader
from app.services.frame_service import frame_service, FrameService
from app.services.subtitle_service import subtitle_service, SubtitleService
from app.services.audio_service import audio_service, AudioService
from app.services.visual_service import visual_service, VisualService
from app.services.alignment_service import alignment_service, AlignmentService
from app.services.metaphor_service import metaphor_service, MetaphorService
from app.services.untranslatability_service import untranslatability_service, UntranslatabilityService
from app.services.corpus_service import corpus_service, CorpusService


__all__ = [
    # Video Services
    "video_service",
    "VideoService",
    "downloader",
    "VideoDownloader",
    # Frame Service
    "frame_service",
    "FrameService",
    # Subtitle Service
    "subtitle_service",
    "SubtitleService",
    # Audio Service
    "audio_service",
    "AudioService",
    # Visual Service
    "visual_service",
    "VisualService",
    # Alignment Service
    "alignment_service",
    "AlignmentService",
    # Metaphor Service
    "metaphor_service",
    "MetaphorService",
    # Untranslatability Service
    "untranslatability_service",
    "UntranslatabilityService",
    # Corpus Service
    "corpus_service",
    "CorpusService",
]