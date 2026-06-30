import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import videos, tasks, corpus, annotations, settings as app_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="多模态语料获取工具 - 视听翻译与隐喻分析",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router, prefix="/api/v1/videos", tags=["videos"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(corpus.router, prefix="/api/v1/corpus", tags=["corpus"])
app.include_router(annotations.router, prefix="/api/v1/annotations", tags=["annotations"])
app.include_router(app_settings.router, tags=["settings"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def _get_ui_dir() -> Path:
    env_ui = os.environ.get("UI_DIR")
    if env_ui:
        return Path(env_ui)
    if getattr(__import__("sys"), "frozen", False):
        return Path(getattr(__import__("sys"), "_MEIPASS", Path(__import__("sys").executable).parent / "_internal")) / "ui"
    return Path(__file__).parent.parent.parent / "ui"


_ui_dir = _get_ui_dir()
if _ui_dir.exists() and _ui_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_ui_dir), html=True), name="ui")
