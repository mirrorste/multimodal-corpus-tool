from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import videos, tasks, corpus, annotations


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


@app.get("/")
async def root():
    return {"message": "多模态语料获取工具 API", "version": settings.PROJECT_VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
