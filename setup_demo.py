#!/usr/bin/env python3
"""
多模态语料获取工具 - Demo 初始化脚本
运行: python setup_demo.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_python_version():
    print("=" * 60)
    print(" 检查 Python 环境")
    print("=" * 60)
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    if version.major >= 3 and version.minor >= 10:
        print("✅ Python 版本符合要求 (>= 3.10)")
        return True
    else:
        print("❌ Python 版本过低，需要 3.10+")
        return False


def install_backend_deps():
    print("\n" + "=" * 60)
    print(" 安装后端依赖")
    print("=" * 60)
    os.chdir(Path(__file__).parent / "backend")

    packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "aiosqlite",
        "pydantic",
        "pydantic-settings",
        "python-multipart",
        "aiofiles",
        "yt-dlp",
        "httpx",
    ]

    print("正在安装依赖，请稍候...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q"] + packages,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print("✅ 后端依赖安装完成")
            return True
        else:
            print(f"❌ 依赖安装失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 安装过程出错: {e}")
        return False


def create_env_file():
    print("\n" + "=" * 60)
    print(" 配置 Demo 环境")
    print("=" * 60)

    backend_dir = Path(__file__).parent / "backend"
    env_path = backend_dir / ".env"

    env_content = """# Demo Environment Configuration
API_HOST=127.0.0.1
API_PORT=8000

# 使用 SQLite 数据库（无需安装 PostgreSQL）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=multimodal_corpus_demo
DB_USER=postgres
DB_PASSWORD=password

# 启用 SQLite 模式（Demo 专用）
USE_SQLITE=true

# 下载与上传目录
DOWNLOAD_DIR=./demo_downloads
UPLOAD_DIR=./demo_uploads
MAX_UPLOAD_SIZE=2048

# 其他配置
FFMPEG_PATH=ffmpeg
LOG_LEVEL=INFO
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"✅ 环境配置文件已创建: {env_path}")

    # 创建目录
    download_dir = backend_dir / "demo_downloads"
    upload_dir = backend_dir / "demo_uploads"
    download_dir.mkdir(exist_ok=True)
    upload_dir.mkdir(exist_ok=True)
    print(f"✅ 下载目录: {download_dir}")
    print(f"✅ 上传目录: {upload_dir}")

    return True


def create_sample_files():
    print("\n" + "=" * 60)
    print(" 创建示例文件")
    print("=" * 60)

    upload_dir = Path(__file__).parent / "backend" / "demo_uploads"

    # 创建一个小的测试视频文件（假数据，用于测试上传功能）
    test_file = upload_dir / "sample_test_video.mp4"
    with open(test_file, "wb") as f:
        # 写入一些假数据（模拟视频文件头）
        f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
        # 填充一些数据
        f.write(b"sample video data for demo testing " * 100)

    print(f"✅ 示例测试文件已创建: {test_file}")
    print(f"   大小: {test_file.stat().st_size} bytes")

    return True


def print_next_steps():
    print("\n" + "=" * 60)
    print(" Demo 环境准备完成！")
    print("=" * 60)
    print("""
下一步操作：

1. 启动后端服务：
   cd backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

2. 打开 Demo 测试页面：
   在浏览器中打开: demo/demo_test.html

3. 运行 API 测试脚本：
   cd backend
   python test_api.py

4. 查看 API 文档：
   http://127.0.0.1:8000/docs

5. 查看测试手册：
   test_manual.md

测试提示：
- 使用 SQLite 数据库，无需安装 PostgreSQL
- 可以在 demo_test.html 页面进行可视化测试
- 测试视频链接建议使用公开的短视频进行测试
- 文件上传可使用 demo_uploads 目录中的示例文件
""")


def main():
    print("\n🎬 多模态语料获取工具 - Demo 环境搭建\n")

    steps = [
        ("检查 Python 版本", check_python_version),
        ("安装后端依赖", install_backend_deps),
        ("配置环境变量", create_env_file),
        ("创建示例文件", create_sample_files),
    ]

    for name, func in steps:
        if not func():
            print(f"\n❌ 步骤失败: {name}")
            print("请根据错误信息修复后重新运行")
            return False

    print_next_steps()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
