import yt_dlp
import os
import asyncio
from typing import Optional, Callable, Dict, Any
from app.core.config import settings
from datetime import datetime


class VideoDownloader:
    PLATFORM_MAP = {
        "youtube": "youtube",
        "bilibili": "bilibili",
        "vimeo": "vimeo",
        "local": "local",
    }

    RESOLUTION_MAP = {
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or settings.DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)

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
        return self.RESOLUTION_MAP.get(resolution, self.RESOLUTION_MAP["1080p"])

    def _build_ydl_opts(
        self,
        resolution: str,
        progress_hook: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        opts = {
            "format": self._get_format(resolution),
            "outtmpl": os.path.join(self.download_dir, "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": False,
            "no_warnings": False,
            "writethumbnail": False,
            "ignoreerrors": False,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
        }
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

        try:
            ydl_opts = self._build_ydl_opts(resolution, progress_hook)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                
                result["success"] = True
                result["file_path"] = file_path
                result["title"] = info.get("title")
                result["duration"] = info.get("duration")
                result["file_size"] = info.get("filesize") or info.get("filesize_approx")
                
                if info.get("height"):
                    result["resolution"] = f"{info['height']}p"

        except yt_dlp.utils.DownloadError as e:
            result["error"] = f"下载失败: {str(e)}"
        except yt_dlp.utils.ExtractorError as e:
            result["error"] = f"提取失败: {str(e)}"
        except Exception as e:
            result["error"] = f"未知错误: {str(e)}"

        return result


downloader = VideoDownloader()
