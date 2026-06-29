import yt_dlp
import os
import shutil
import re
import subprocess
from typing import Optional, Callable, Dict, Any
from app.core.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def sanitize_filename(title: str) -> str:
    if not title:
        return ""
    filename = title.strip()
    filename = re.sub(r'\s+', '_', filename)
    filename = re.sub(r'[\\/:*?"<>|]', '', filename)
    filename = filename.replace('\n', '_').replace('\r', '_')
    if len(filename) > 150:
        filename = filename[:150]
    return filename


def check_ffmpeg() -> bool:
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
        return True
    if shutil.which("ffmpeg"):
        return True
    return False


class VideoDownloader:
    PLATFORM_MAP = {
        "youtube": "youtube",
        "bilibili": "bilibili",
        "vimeo": "vimeo",
        "local": "local",
    }

    RESOLUTION_MAP_WITH_FFMPEG = {
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }

    RESOLUTION_MAP_WITHOUT_FFMPEG = {
        "2160p": "best[height<=2160]",
        "1440p": "best[height<=1440]",
        "1080p": "best[height<=1080]",
        "720p": "best[height<=720]",
        "480p": "best[height<=480]",
        "360p": "best[height<=360]",
    }

    def __init__(self, download_dir: Optional[str] = None, cookies_file: Optional[str] = None):
        self.download_dir = download_dir or settings.DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)
        self.has_ffmpeg = check_ffmpeg()
        self.cookies_file = cookies_file or getattr(settings, "COOKIES_FILE", None)
        if self.cookies_file and os.path.exists(self.cookies_file):
            logger.info(f"使用 cookies 文件: {self.cookies_file}")
        if not self.has_ffmpeg:
            logger.warning("未检测到 ffmpeg，将使用单文件格式下载（画质可能较低）")
        else:
            logger.info("检测到 ffmpeg，将使用最佳画质合并下载")

    def detect_platform(self, url: str) -> str:
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "bilibili.com" in url_lower or "b23.tv" in url_lower:
            return "bilibili"
        elif "vimeo.com" in url_lower:
            return "vimeo"
        else:
            return "unknown"

    def _get_format(self, resolution: str) -> str:
        if self.has_ffmpeg:
            return self.RESOLUTION_MAP_WITH_FFMPEG.get(
                resolution, self.RESOLUTION_MAP_WITH_FFMPEG["1080p"]
            )
        else:
            return self.RESOLUTION_MAP_WITHOUT_FFMPEG.get(
                resolution, self.RESOLUTION_MAP_WITHOUT_FFMPEG["1080p"]
            )

    def _build_ydl_opts(
        self,
        resolution: str,
        progress_hook: Optional[Callable] = None,
        outtmpl: Optional[str] = None,
    ) -> Dict[str, Any]:
        opts = {
            "format": self._get_format(resolution),
            "outtmpl": outtmpl or os.path.join(self.download_dir, "%(title).150B.%(ext)s"),
            "noplaylist": True,
            "quiet": False,
            "no_warnings": False,
            "writethumbnail": False,
            "ignoreerrors": False,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
            "extractor_retries": 3,
        }
        if self.cookies_file and os.path.exists(self.cookies_file):
            opts["cookiefile"] = self.cookies_file
        ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
        if ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path):
            opts["ffmpeg_location"] = ffmpeg_path
        if progress_hook:
            opts["progress_hooks"] = [progress_hook]
        return opts

    def get_video_info(self, url: str) -> Dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "webpage_url": info.get("webpage_url"),
                "id": info.get("id"),
                "ext": info.get("ext"),
            }

    def download_video(
        self,
        url: str,
        resolution: str = "1080p",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "file_path": None,
            "title": None,
            "duration": None,
            "resolution": resolution,
            "file_size": None,
            "error": None,
        }

        def progress_hook(d):
            if progress_callback:
                progress_data = {
                    "status": d.get("status"),
                    "downloaded_bytes": d.get("downloaded_bytes", 0),
                    "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate", 0),
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "filename": d.get("filename"),
                }
                progress_callback(progress_data)

        def _do_download(use_ffmpeg: bool = True):
            if not use_ffmpeg:
                original_ffmpeg = self.has_ffmpeg
                self.has_ffmpeg = False
            try:
                ydl_opts = self._build_ydl_opts(resolution, progress_hook)
                logger.info(f"开始下载视频: {url}, 分辨率: {resolution}")
                logger.info(f"使用格式: {ydl_opts['format']}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)

                    title = info.get("title", "")
                    clean_name = sanitize_filename(title)
                    if clean_name and os.path.exists(file_path):
                        ext = os.path.splitext(file_path)[1]
                        new_path = os.path.join(self.download_dir, clean_name + ext)
                        if new_path != file_path:
                            try:
                                if os.path.exists(new_path):
                                    os.remove(new_path)
                                os.rename(file_path, new_path)
                                file_path = new_path
                            except Exception as e:
                                logger.warning(f"重命名文件失败: {e}")

                    result["success"] = True
                    result["file_path"] = file_path
                    result["title"] = title
                    result["duration"] = info.get("duration")
                    result["file_size"] = info.get("filesize") or info.get("filesize_approx")

                    if info.get("height"):
                        result["resolution"] = f"{info['height']}p"

                    logger.info(f"下载成功: {result['title']}, 文件: {file_path}")
                    return True
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"下载失败: {error_msg}")
                if use_ffmpeg and "ffmpeg" in error_msg.lower():
                    logger.warning("ffmpeg 相关错误，尝试降级到单文件格式重试")
                    if _do_download(use_ffmpeg=False):
                        return True
                result["error"] = f"下载失败: {error_msg}"
            except yt_dlp.utils.ExtractorError as e:
                error_msg = str(e)
                logger.error(f"提取失败: {error_msg}")
                result["error"] = f"提取失败: {error_msg}"
            except Exception as e:
                error_msg = str(e)
                logger.error(f"未知错误: {error_msg}", exc_info=True)
                result["error"] = f"未知错误: {error_msg}"
            finally:
                if not use_ffmpeg:
                    self.has_ffmpeg = original_ffmpeg
            return False

        _do_download(use_ffmpeg=True)
        return result


def _get_cookies_file():
    import os
    import json
    from pathlib import Path
    settings_file = Path(__file__).parent.parent.parent / "data" / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                cookies_path = settings.get("cookies", {}).get("cookies_file")
                if cookies_path and os.path.exists(cookies_path):
                    return cookies_path
        except:
            pass
    return None


downloader = VideoDownloader(cookies_file=_get_cookies_file())
