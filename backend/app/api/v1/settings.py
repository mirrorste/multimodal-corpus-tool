from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import json
from pathlib import Path

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

SETTINGS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "settings.json"

class CookiesConfig(BaseModel):
    cookies_file: Optional[str] = None

def _load_settings():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

@router.get("/cookies")
async def get_cookies_config():
    settings = _load_settings()
    return settings.get("cookies", {})

@router.post("/cookies")
async def save_cookies_config(config: CookiesConfig):
    settings = _load_settings()
    if "cookies" not in settings:
        settings["cookies"] = {}
    settings["cookies"]["cookies_file"] = config.cookies_file
    _save_settings(settings)
    return {"message": "设置已保存"}

@router.get("/")
async def get_settings():
    return _load_settings()

@router.post("/")
async def save_settings(data: dict):
    settings = _load_settings()
    settings.update(data)
    _save_settings(settings)
    return {"message": "设置已保存"}
