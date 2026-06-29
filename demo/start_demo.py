#!/usr/bin/env python3
"""
多模态语料获取工具 - Demo 启动脚本
"""

import subprocess
import sys
import os
import webbrowser
import time
from pathlib import Path


def check_dependencies():
    print("=" * 60)
    print(" 检查依赖")
    print("=" * 60)
    required = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "aiosqlite",
        "pydantic",
        "pydantic_settings",
        "yt_dlp",
    ]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_").replace(".", "_"))
            print(f"  ✅ {pkg}")
        except ImportError:
            missing.append(pkg)
            print(f"  ❌ {pkg} (未安装)")

    if missing:
        print(f"\n缺少 {len(missing)} 个依赖，正在安装...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q"] + missing,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("✅ 依赖安装完成")
        else:
            print(f"❌ 依赖安装失败: {result.stderr}")
            return False
    else:
        print("\n✅ 所有依赖已就绪")

    return True


def start_backend():
    print("\n" + "=" * 60)
    print(" 启动后端服务")
    print("=" * 60)

    backend_dir = Path(__file__).parent.parent / "backend"
    os.chdir(backend_dir)

    # 确保 .env 存在
    env_path = backend_dir / ".env"
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write("USE_SQLITE=true\n")
            f.write("DOWNLOAD_DIR=./demo_downloads\n")
            f.write("UPLOAD_DIR=./demo_uploads\n")
        print("✅ 已创建默认 .env 配置")

    print("🚀 启动 FastAPI 服务...")
    print("📡 服务地址: http://127.0.0.1:8000")
    print("📖 API 文档: http://127.0.0.1:8000/docs")
    print("🧪 Demo 页面: demo/demo_test.html")
    print("\n按 Ctrl+C 停止服务\n")

    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload",
        ])
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")


def main():
    print("\n🎬 多模态语料获取工具 - Demo 启动器\n")

    if not check_dependencies():
        print("\n❌ 依赖检查失败，请手动安装依赖")
        return

    start_backend()


if __name__ == "__main__":
    main()
