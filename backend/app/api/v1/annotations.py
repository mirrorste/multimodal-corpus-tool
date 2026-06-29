from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter()


@router.get("/metaphors")
async def get_metaphor_annotations(db: AsyncSession = Depends(get_db)):
    return {"message": "隐喻标注查询功能开发中"}


@router.put("/metaphors/{annotation_id}")
async def update_metaphor_annotation(annotation_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": "隐喻标注更新功能开发中", "annotation_id": annotation_id}


@router.get("/untranslatability")
async def get_untranslatability_annotations(db: AsyncSession = Depends(get_db)):
    return {"message": "不可译性标注查询功能开发中"}


@router.put("/untranslatability/{annotation_id}")
async def update_untranslatability_annotation(annotation_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": "不可译性标注更新功能开发中", "annotation_id": annotation_id}
