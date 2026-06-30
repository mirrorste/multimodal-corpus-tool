import os
import sys
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
DEMO_DIR = PROJECT_ROOT / "demo"
OUTPUT_DIR = PROJECT_ROOT / "dist"
APP_NAME = "多模态语料收集工具"

EXCLUDES = [
    "paddleocr",
    "paddle",
    "paddlepaddle",
    "torch",
    "torchvision",
    "torchaudio",
    "transformers",
    "whisper",
    "openai-whisper",
    "scipy",
    "PIL",
    "pillow",
    "pandas",
    "matplotlib",
    "cv2",
    "opencv-python",
    "ffmpeg-python",
    "asyncpg",
    "redis",
    "celery",
    "alembic",
    "pytest",
    "setuptools",
    "distutils",
]

HIDDEN_IMPORTS = [
    "aiosqlite",
]

INCLUDE_DATA = [
    (str(DEMO_DIR), "demo"),
]


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--clean",
        "--noconfirm",
        "--onedir",
        "--paths", str(BASE_DIR),
    ]

    for exc in EXCLUDES:
        cmd.extend(["--exclude-module", exc])

    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    for src, dst in INCLUDE_DATA:
        sep = ";" if sys.platform == "win32" else ":"
        cmd.extend(["--add-data", f"{src}{sep}{dst}"])

    cmd.append(str(BASE_DIR / "launcher.py"))

    print("执行打包命令:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    if result.returncode != 0:
        print("打包失败！")
        sys.exit(1)

    print("\n打包完成！")
    dist_path = BASE_DIR / "dist" / APP_NAME
    print(f"输出目录: {dist_path}")

    final_dir = OUTPUT_DIR / APP_NAME
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if final_dir.exists():
        shutil.rmtree(final_dir)

    shutil.copytree(dist_path, final_dir)
    print(f"已复制到: {final_dir}")

    exe_path = final_dir / f"{APP_NAME}.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n可执行文件: {exe_path}")
        print(f"文件大小: {size_mb:.1f} MB")


if __name__ == "__main__":
    build()
