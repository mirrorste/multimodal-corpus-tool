import os
import sys
import threading
from pathlib import Path


def get_app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_resource_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent / "_internal"))
    return Path(__file__).parent.parent


APP_DIR = get_app_dir()
RESOURCE_DIR = get_resource_dir()
DATA_DIR = APP_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "multimodal_corpus.db"
UI_DIR = RESOURCE_DIR / "ui"
FFMPEG_DIR = RESOURCE_DIR / "ffmpeg"

os.environ["USE_SQLITE"] = "true"
os.environ["DOWNLOAD_DIR"] = str(DOWNLOAD_DIR)
os.environ["UPLOAD_DIR"] = str(UPLOAD_DIR)
os.environ["DB_PATH"] = str(DB_PATH)
os.environ["API_HOST"] = "127.0.0.1"
os.environ["API_PORT"] = "8765"

ffmpeg_exe = FFMPEG_DIR / "ffmpeg.exe"
if ffmpeg_exe.exists():
    os.environ["FFMPEG_PATH"] = str(ffmpeg_exe)
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def start_backend():
    import uvicorn
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


def main():
    import webview

    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    import time
    time.sleep(2)

    html_path = UI_DIR / "app.html"

    window = webview.create_window(
        title="视频下载工具",
        url=f"file:///{html_path.as_posix()}",
        width=1280,
        height=800,
        min_size=(1024, 680),
        resizable=True,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    main()
