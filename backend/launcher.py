import os
import sys
import threading
import webbrowser
import time
import http.server
import socketserver
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
DEMO_DIR = RESOURCE_DIR / "demo"

os.environ["USE_SQLITE"] = "true"
os.environ["DOWNLOAD_DIR"] = str(DOWNLOAD_DIR)
os.environ["UPLOAD_DIR"] = str(UPLOAD_DIR)
os.environ["DB_PATH"] = str(DB_PATH)
os.environ["API_HOST"] = "127.0.0.1"
os.environ["API_PORT"] = "8000"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def start_demo_server(port=8080):
    os.chdir(str(DEMO_DIR))
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    httpd.serve_forever()


def main():
    import uvicorn
    from app.main import app

    demo_port = 8080
    api_port = 8000

    demo_thread = threading.Thread(target=start_demo_server, args=(demo_port,), daemon=True)
    demo_thread.start()
    print(f"[Demo] 页面已启动: http://127.0.0.1:{demo_port}/demo_test.html")

    def open_browser():
        time.sleep(2)
        webbrowser.open(f"http://127.0.0.1:{demo_port}/demo_test.html")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print(f"[API] 服务已启动: http://127.0.0.1:{api_port}")
    print(f"[数据] 数据目录: {DATA_DIR}")
    print("=" * 60)
    print("  多模态语料收集工具 - 视频批量下载版")
    print("  浏览器将自动打开，如未打开请手动访问上面的地址")
    print("  关闭此窗口即可退出程序")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=api_port, log_level="info")


if __name__ == "__main__":
    main()
