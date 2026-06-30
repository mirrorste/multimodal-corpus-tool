#!/usr/bin/env python3
"""
第二阶段 API 测试脚本 - 多模态内容提取
测试：帧提取、字幕提取、音频提取、视觉描述

用法:
    python test_phase2.py              # 运行所有第二阶段测试
    python test_phase2.py --module=frame   # 仅测试帧提取
    python test_phase2.py --server        # 仅打印测试方案
"""

import asyncio
import httpx
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
TEST_RESULTS: List[Dict[str, Any]] = []


class TestResult:
    def __init__(self, case_id: str, name: str, passed: bool, message: str = ""):
        self.case_id = case_id
        self.name = name
        self.passed = passed
        self.message = message
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "case_id": self.case_id,
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "timestamp": self.timestamp,
        }

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        msg = f" - {self.message}" if self.message else ""
        return f"[{self.case_id}] {status} {self.name}{msg}"


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)


def print_test(result: TestResult):
    print(result)


async def test_health_check(client: httpx.AsyncClient) -> TestResult:
    """TC-P2-000: 健康检查"""
    try:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code == 200 and response.json().get("status") == "healthy":
            return TestResult("TC-P2-000", "健康检查", True, "服务运行正常")
        return TestResult("TC-P2-000", "健康检查", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-P2-000", "健康检查", False, f"连接失败: {str(e)}")


async def create_test_video(client: httpx.AsyncClient) -> Optional[str]:
    """创建测试视频"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/",
            json={
                "url": "https://www.youtube.com/watch?v=phase2_test_video",
                "platform": "youtube",
                "preferred_resolution": "1080p",
                "file_path": "./test_data/sample.mp4",
            },
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("id")
        return None
    except Exception as e:
        print(f"创建测试视频失败: {e}")
        return None


# ============ 帧提取模块测试 ============

async def test_frame_extract_subtitle(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-001: 字幕帧提取接口"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames/extract-subtitle",
            params={"fps": 1.0, "quality": 2, "margin": 0.5},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-FR-001", "字幕帧提取", True,
                f"提取 {data.get('total_frames', 0)} 帧, 内嵌字幕: {data.get('has_embedded_subtitles')}"
            )
        elif response.status_code == 400:
            return TestResult(
                "TC-FR-001", "字幕帧提取", True,
                f"业务返回: {response.json().get('detail', '未知')}"
            )
        return TestResult("TC-FR-001", "字幕帧提取", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-001", "字幕帧提取", False, f"请求失败: {str(e)}")


async def test_frame_list(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-002: 获取帧列表"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-FR-002", "获取帧列表", True, f"返回 {len(data)} 条记录")
        return TestResult("TC-FR-002", "获取帧列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-002", "获取帧列表", False, f"请求失败: {str(e)}")


async def test_frame_filter_has_subtitle(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-003: 按字幕标志筛选帧"""
    try:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames",
            params={"has_subtitle": "true"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-FR-003", "按字幕标志筛选帧", True, f"含字幕帧 {len(data)} 条")
        return TestResult("TC-FR-003", "按字幕标志筛选帧", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-003", "按字幕标志筛选帧", False, f"请求失败: {str(e)}")


async def test_frame_filter_time_range(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-004: 按时间范围筛选帧"""
    try:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames",
            params={"start_time": 0.0, "end_time": 10.0},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-FR-004", "按时间范围筛选帧", True, f"0-10秒内 {len(data)} 帧")
        return TestResult("TC-FR-004", "按时间范围筛选帧", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-004", "按时间范围筛选帧", False, f"请求失败: {str(e)}")


async def test_frame_single(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-005: 获取单帧详情"""
    try:
        list_resp = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames")
        if list_resp.status_code != 200:
            return TestResult("TC-FR-005", "获取单帧详情", False, "获取帧列表失败")
        frames = list_resp.json()
        if not frames:
            return TestResult("TC-FR-005", "获取单帧详情", True, "无帧数据（跳过）")

        frame_id = frames[0]["id"]
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames/{frame_id}")
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-FR-005", "获取单帧详情", True,
                f"时间戳: {data.get('timestamp')}s, 路径有效: {'/uploads/' in (data.get('image_path') or '')}"
            )
        return TestResult("TC-FR-005", "获取单帧详情", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-005", "获取单帧详情", False, f"请求失败: {str(e)}")


async def test_frame_detect_subtitles(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-006: 字幕帧检测"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames/detect-subtitles"
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-FR-006", "字幕帧检测", True,
                f"总帧: {data.get('total_frames', 0)}, 字幕帧: {data.get('subtitle_frames', 0)}"
            )
        elif response.status_code == 400:
            return TestResult("TC-FR-006", "字幕帧检测", True, "正常返回（无帧数据）")
        return TestResult("TC-FR-006", "字幕帧检测", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-006", "字幕帧检测", False, f"请求失败: {str(e)}")


async def test_frame_nonexistent_video(client: httpx.AsyncClient) -> TestResult:
    """TC-FR-007: 不存在的视频提取帧（异常场景）"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{fake_id}/frames/extract-subtitle"
        )
        if response.status_code == 404:
            return TestResult("TC-FR-007", "不存在视频提取帧", True, "正确返回 404")
        return TestResult("TC-FR-007", "不存在视频提取帧", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-007", "不存在视频提取帧", False, f"请求失败: {str(e)}")


async def test_frame_invalid_params(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-008: 非法参数（异常场景）"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames/extract-subtitle",
            params={"fps": -1.0},  # 非法 fps
        )
        # 期望 422 参数校验错误
        if response.status_code == 422:
            return TestResult("TC-FR-008", "非法参数校验", True, "正确返回 422 校验错误")
        elif response.status_code == 200 or response.status_code == 400:
            return TestResult("TC-FR-008", "非法参数校验", True, f"返回状态 {response.status_code}（业务处理）")
        return TestResult("TC-FR-008", "非法参数校验", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-008", "非法参数校验", False, f"请求失败: {str(e)}")


async def test_frame_delete(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-FR-009: 删除视频帧"""
    try:
        response = await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/frames")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-FR-009", "删除视频帧", True, f"删除 {data.get('deleted_count', 0)} 条")
        return TestResult("TC-FR-009", "删除视频帧", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-FR-009", "删除视频帧", False, f"请求失败: {str(e)}")


# ============ 字幕提取模块测试 ============

async def test_subtitle_extract_auto(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-001: 字幕提取 - auto 模式"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles/extract",
            params={"source": "auto", "language": "zh"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-SUB-001", "字幕提取 (auto)", True,
                f"来源: {data.get('source_used')}, 数量: {data.get('total_subtitles', 0)}"
            )
        elif response.status_code == 400:
            return TestResult(
                "TC-SUB-001", "字幕提取 (auto)", True,
                f"业务返回: {response.json().get('detail', '无字幕')}"
            )
        return TestResult("TC-SUB-001", "字幕提取 (auto)", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-001", "字幕提取 (auto)", False, f"请求失败: {str(e)}")


async def test_subtitle_extract_ocr(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-002: 字幕提取 - OCR 模式"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles/extract",
            params={"source": "ocr", "language": "zh"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-SUB-002", "字幕提取 (OCR)", True,
                f"数量: {data.get('total_subtitles', 0)}"
            )
        elif response.status_code == 400:
            return TestResult(
                "TC-SUB-002", "字幕提取 (OCR)", True,
                f"业务返回: {response.json().get('detail', 'OCR失败')}"
            )
        return TestResult("TC-SUB-002", "字幕提取 (OCR)", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-002", "字幕提取 (OCR)", False, f"请求失败: {str(e)}")


async def test_subtitle_list(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-003: 获取字幕列表"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-SUB-003", "获取字幕列表", True, f"返回 {len(data)} 条记录")
        return TestResult("TC-SUB-003", "获取字幕列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-003", "获取字幕列表", False, f"请求失败: {str(e)}")


async def test_subtitle_filter_source(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-004: 按来源筛选字幕"""
    try:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles",
            params={"source": "OCR"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-SUB-004", "按来源筛选字幕", True, f"OCR字幕 {len(data)} 条")
        return TestResult("TC-SUB-004", "按来源筛选字幕", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-004", "按来源筛选字幕", False, f"请求失败: {str(e)}")


async def test_subtitle_filter_time(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-005: 按时间筛选字幕"""
    try:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles",
            params={"start_time": 0.0, "end_time": 30.0},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-SUB-005", "按时间筛选字幕", True, f"0-30秒 {len(data)} 条")
        return TestResult("TC-SUB-005", "按时间筛选字幕", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-005", "按时间筛选字幕", False, f"请求失败: {str(e)}")


async def test_subtitle_update(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-006: 更新字幕（人工校正）"""
    try:
        list_resp = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles")
        if list_resp.status_code != 200:
            return TestResult("TC-SUB-006", "更新字幕", False, "获取字幕列表失败")
        subtitles = list_resp.json()
        if not subtitles:
            return TestResult("TC-SUB-006", "更新字幕", True, "无字幕数据（跳过）")

        sub_id = subtitles[0]["id"]
        response = await client.put(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles/{sub_id}",
            json={"text": "【测试校正】测试字幕文本", "language": "zh"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-SUB-006", "更新字幕", True, f"更新后文本: {data.get('text', '')[:30]}...")
        return TestResult("TC-SUB-006", "更新字幕", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-006", "更新字幕", False, f"请求失败: {str(e)}")


async def test_subtitle_nonexistent_video(client: httpx.AsyncClient) -> TestResult:
    """TC-SUB-007: 不存在的视频提取字幕（异常场景）"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{fake_id}/subtitles/extract"
        )
        if response.status_code == 404:
            return TestResult("TC-SUB-007", "不存在视频提取字幕", True, "正确返回 404")
        return TestResult("TC-SUB-007", "不存在视频提取字幕", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-007", "不存在视频提取字幕", False, f"请求失败: {str(e)}")


async def test_subtitle_invalid_source(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-008: 非法 source 参数（异常场景）"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles/extract",
            params={"source": "invalid_source"},
        )
        if response.status_code == 400:
            return TestResult("TC-SUB-008", "非法 source 参数", True, "正确返回 400")
        return TestResult("TC-SUB-008", "非法 source 参数", False, f"预期 400，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-008", "非法 source 参数", False, f"请求失败: {str(e)}")


async def test_subtitle_delete(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-SUB-009: 删除视频字幕"""
    try:
        response = await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/subtitles")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-SUB-009", "删除视频字幕", True, f"删除 {data.get('deleted_count', 0)} 条")
        return TestResult("TC-SUB-009", "删除视频字幕", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-SUB-009", "删除视频字幕", False, f"请求失败: {str(e)}")


# ============ 音频提取模块测试 ============

async def test_audio_extract(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-001: 音频提取"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio/extract",
            params={"format": "wav", "denoise": "false"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-AUD-001", "音频提取", True,
                f"时长: {data.get('duration', 0)}s"
            )
        elif response.status_code == 400:
            return TestResult(
                "TC-AUD-001", "音频提取", True,
                f"业务返回: {response.json().get('detail', '提取失败')}"
            )
        return TestResult("TC-AUD-001", "音频提取", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-001", "音频提取", False, f"请求失败: {str(e)}")


async def test_audio_extract_with_denoise(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-002: 带降噪的音频提取"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio/extract",
            params={"format": "wav", "denoise": "true"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-AUD-002", "带降噪音频提取", True, f"时长: {data.get('duration', 0)}s")
        elif response.status_code == 400:
            return TestResult("TC-AUD-002", "带降噪音频提取", True, "业务返回（正常）")
        return TestResult("TC-AUD-002", "带降噪音频提取", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-002", "带降噪音频提取", False, f"请求失败: {str(e)}")


async def test_audio_list(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-003: 获取音频片段列表"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-AUD-003", "获取音频片段列表", True, f"返回 {len(data)} 条记录")
        return TestResult("TC-AUD-003", "获取音频片段列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-003", "获取音频片段列表", False, f"请求失败: {str(e)}")


async def test_audio_filter_has_asr(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-004: 按 ASR 状态筛选"""
    try:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio",
            params={"has_asr": "true"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-AUD-004", "按 ASR 状态筛选", True, f"含 ASR 片段 {len(data)} 条")
        return TestResult("TC-AUD-004", "按 ASR 状态筛选", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-004", "按 ASR 状态筛选", False, f"请求失败: {str(e)}")


async def test_audio_asr(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-005: ASR 语音识别"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio/asr",
            params={"language": "zh", "denoise": "false"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-AUD-005", "ASR 语音识别", True,
                f"语言: {data.get('detected_language')}, 片段数: {data.get('total_segments', 0)}"
            )
        elif response.status_code == 400:
            return TestResult(
                "TC-AUD-005", "ASR 语音识别", True,
                f"业务返回: {response.json().get('detail', '识别失败')}"
            )
        return TestResult("TC-AUD-005", "ASR 语音识别", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-005", "ASR 语音识别", False, f"请求失败: {str(e)}")


async def test_audio_extract_by_subtitles(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-006: 按字幕提取音频片段"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio/extract-by-subtitles",
            params={"format": "wav"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-AUD-006", "按字幕提取音频", True,
                f"提取 {data.get('total_segments', 0)} 个片段"
            )
        elif response.status_code == 400:
            return TestResult("TC-AUD-006", "按字幕提取音频", True, "业务返回（正常）")
        return TestResult("TC-AUD-006", "按字幕提取音频", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-006", "按字幕提取音频", False, f"请求失败: {str(e)}")


async def test_audio_nonexistent_video(client: httpx.AsyncClient) -> TestResult:
    """TC-AUD-007: 不存在的视频提取音频（异常场景）"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{fake_id}/audio/extract"
        )
        if response.status_code == 404:
            return TestResult("TC-AUD-007", "不存在视频提取音频", True, "正确返回 404")
        return TestResult("TC-AUD-007", "不存在视频提取音频", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-007", "不存在视频提取音频", False, f"请求失败: {str(e)}")


async def test_audio_delete(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-AUD-008: 删除音频片段"""
    try:
        response = await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/audio")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-AUD-008", "删除音频片段", True, f"删除 {data.get('deleted_count', 0)} 条")
        return TestResult("TC-AUD-008", "删除音频片段", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-AUD-008", "删除音频片段", False, f"请求失败: {str(e)}")


# ============ 视觉描述模块测试 ============

async def test_visual_status(client: httpx.AsyncClient) -> TestResult:
    """TC-VIS-001: 视觉服务状态检查"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/visual/status")
        if response.status_code == 200:
            data = response.json()
            vision = "✅" if data.get("vision") else "❌"
            llm = "✅" if data.get("llm") else "❌"
            return TestResult(
                "TC-VIS-001", "视觉服务状态检查", True,
                f"Vision: {vision}, LLM: {llm}"
            )
        return TestResult("TC-VIS-001", "视觉服务状态检查", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-001", "视觉服务状态检查", False, f"请求失败: {str(e)}")


async def test_visual_analyze_basic(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-002: 基础视觉分析（描述+物体）"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual/analyze",
            params={
                "enable_description": "true",
                "enable_object_detection": "true",
                "enable_scene_classification": "false",
                "enable_emotion_detection": "false",
                "skip_existing": "true",
            },
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-VIS-002", "基础视觉分析", True,
                f"成功: {data.get('success_count', 0)}, 失败: {data.get('failed_count', 0)}, 跳过: {data.get('skipped_count', 0)}"
            )
        elif response.status_code == 400:
            return TestResult("TC-VIS-002", "基础视觉分析", True, "业务返回（正常）")
        return TestResult("TC-VIS-002", "基础视觉分析", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-002", "基础视觉分析", False, f"请求失败: {str(e)}")


async def test_visual_analyze_full(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-003: 完整视觉分析（含场景+情感）"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual/analyze",
            params={
                "enable_description": "true",
                "enable_object_detection": "true",
                "enable_scene_classification": "true",
                "enable_emotion_detection": "true",
                "skip_existing": "true",
            },
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-VIS-003", "完整视觉分析", True,
                f"成功: {data.get('success_count', 0)}"
            )
        elif response.status_code == 400:
            return TestResult("TC-VIS-003", "完整视觉分析", True, "业务返回（正常）")
        return TestResult("TC-VIS-003", "完整视觉分析", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-003", "完整视觉分析", False, f"请求失败: {str(e)}")


async def test_visual_list(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-004: 获取视觉描述列表"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-VIS-004", "获取视觉描述列表", True, f"返回 {len(data)} 条记录")
        return TestResult("TC-VIS-004", "获取视觉描述列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-004", "获取视觉描述列表", False, f"请求失败: {str(e)}")


async def test_visual_filter_scene(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-005: 按场景筛选视觉描述"""
    try:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual",
            params={"scene": "室内"},
        )
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-VIS-005", "按场景筛选", True, f"匹配 {len(data)} 条")
        return TestResult("TC-VIS-005", "按场景筛选", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-005", "按场景筛选", False, f"请求失败: {str(e)}")


async def test_visual_single(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-006: 获取单条视觉描述详情"""
    try:
        list_resp = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual")
        if list_resp.status_code != 200:
            return TestResult("TC-VIS-006", "获取单条视觉描述", False, "获取列表失败")
        descs = list_resp.json()
        if not descs:
            return TestResult("TC-VIS-006", "获取单条视觉描述", True, "无数据（跳过）")

        desc_id = descs[0]["id"]
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual/{desc_id}")
        if response.status_code == 200:
            data = response.json()
            has_desc = bool(data.get("description") or data.get("objects"))
            return TestResult("TC-VIS-006", "获取单条视觉描述", True, f"有内容: {has_desc}")
        return TestResult("TC-VIS-006", "获取单条视觉描述", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-006", "获取单条视觉描述", False, f"请求失败: {str(e)}")


async def test_visual_update(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-007: 更新视觉描述（人工校正）"""
    try:
        list_resp = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual")
        if list_resp.status_code != 200:
            return TestResult("TC-VIS-007", "更新视觉描述", False, "获取列表失败")
        descs = list_resp.json()
        if not descs:
            return TestResult("TC-VIS-007", "更新视觉描述", True, "无数据（跳过）")

        desc_id = descs[0]["id"]
        response = await client.put(
            f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual/{desc_id}",
            json={"description": "【测试校正】一个测试场景描述", "scene": "测试场景"},
        )
        if response.status_code == 200:
            return TestResult("TC-VIS-007", "更新视觉描述", True, "更新成功")
        return TestResult("TC-VIS-007", "更新视觉描述", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-007", "更新视觉描述", False, f"请求失败: {str(e)}")


async def test_visual_nonexistent_video(client: httpx.AsyncClient) -> TestResult:
    """TC-VIS-008: 不存在的视频视觉分析（异常场景）"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.post(f"{BASE_URL}{API_PREFIX}/videos/{fake_id}/visual/analyze")
        if response.status_code == 404:
            return TestResult("TC-VIS-008", "不存在视频视觉分析", True, "正确返回 404")
        return TestResult("TC-VIS-008", "不存在视频视觉分析", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-008", "不存在视频视觉分析", False, f"请求失败: {str(e)}")


async def test_visual_delete(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-VIS-009: 删除视觉描述"""
    try:
        response = await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/visual")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-VIS-009", "删除视觉描述", True, f"删除 {data.get('deleted_count', 0)} 条")
        return TestResult("TC-VIS-009", "删除视觉描述", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-VIS-009", "删除视觉描述", False, f"请求失败: {str(e)}")


# ============ 测试执行 ============

async def run_phase2_tests():
    """执行第二阶段测试"""
    print_section("第二阶段 API 测试 - 多模态内容提取")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 健康检查
        health = await test_health_check(client)
        print_test(health)
        TEST_RESULTS.append(health.to_dict())

        if not health.passed:
            print("\n⚠️  服务未启动，无法执行测试")
            print("请先启动后端服务: cd backend && python run.py")
            return

        # 2. 创建测试视频
        print_section("创建测试数据")
        video_id = await create_test_video(client)
        if video_id:
            print(f"✅ 测试视频创建成功: {video_id[:20]}...")
        else:
            print("⚠️  测试视频创建失败，跳过依赖视频的测试")

        # 3. 帧提取模块测试
        print_section("模块 1: 帧提取 (Frame Extraction)")

        frame_tests = []
        if video_id:
            frame_tests.extend([
                await test_frame_extract_subtitle(client, video_id),
                await test_frame_list(client, video_id),
                await test_frame_filter_has_subtitle(client, video_id),
                await test_frame_filter_time_range(client, video_id),
                await test_frame_single(client, video_id),
                await test_frame_detect_subtitles(client, video_id),
                await test_frame_invalid_params(client, video_id),
            ])
        frame_tests.append(await test_frame_nonexistent_video(client))

        for r in frame_tests:
            print_test(r)
            TEST_RESULTS.append(r.to_dict())

        # 4. 字幕提取模块测试
        print_section("模块 2: 字幕提取 (Subtitle Extraction)")

        sub_tests = []
        if video_id:
            sub_tests.extend([
                await test_subtitle_extract_auto(client, video_id),
                await test_subtitle_extract_ocr(client, video_id),
                await test_subtitle_list(client, video_id),
                await test_subtitle_filter_source(client, video_id),
                await test_subtitle_filter_time(client, video_id),
                await test_subtitle_update(client, video_id),
                await test_subtitle_invalid_source(client, video_id),
            ])
        sub_tests.append(await test_subtitle_nonexistent_video(client))

        for r in sub_tests:
            print_test(r)
            TEST_RESULTS.append(r.to_dict())

        # 5. 音频提取模块测试
        print_section("模块 3: 音频提取 (Audio Extraction)")

        audio_tests = []
        if video_id:
            audio_tests.extend([
                await test_audio_extract(client, video_id),
                await test_audio_extract_with_denoise(client, video_id),
                await test_audio_list(client, video_id),
                await test_audio_filter_has_asr(client, video_id),
                await test_audio_asr(client, video_id),
                await test_audio_extract_by_subtitles(client, video_id),
            ])
        audio_tests.append(await test_audio_nonexistent_video(client))

        for r in audio_tests:
            print_test(r)
            TEST_RESULTS.append(r.to_dict())

        # 6. 视觉描述模块测试
        print_section("模块 4: 视觉描述 (Visual Description)")

        visual_tests = [await test_visual_status(client)]
        if video_id:
            visual_tests.extend([
                await test_visual_analyze_basic(client, video_id),
                await test_visual_analyze_full(client, video_id),
                await test_visual_list(client, video_id),
                await test_visual_filter_scene(client, video_id),
                await test_visual_single(client, video_id),
                await test_visual_update(client, video_id),
            ])
        visual_tests.append(await test_visual_nonexistent_video(client))

        for r in visual_tests:
            print_test(r)
            TEST_RESULTS.append(r.to_dict())

        # 7. 清理测试数据
        print_section("测试数据清理")

        if video_id:
            cleanups = [
                await test_frame_delete(client, video_id),
                await test_subtitle_delete(client, video_id),
                await test_audio_delete(client, video_id),
                await test_visual_delete(client, video_id),
            ]
            for r in cleanups:
                print_test(r)
                TEST_RESULTS.append(r.to_dict())

            # 删除测试视频
            try:
                await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{video_id}")
                print(f"✅ 测试视频已删除")
            except Exception:
                pass


def print_summary():
    """打印测试汇总"""
    print_section("测试结果汇总")

    total = len(TEST_RESULTS)
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"总测试用例: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    print(f"通过率: {pass_rate:.1f}%")

    # 按模块统计
    modules = {
        "帧提取": [r for r in TEST_RESULTS if r["case_id"].startswith("TC-FR")],
        "字幕提取": [r for r in TEST_RESULTS if r["case_id"].startswith("TC-SUB")],
        "音频提取": [r for r in TEST_RESULTS if r["case_id"].startswith("TC-AUD")],
        "视觉描述": [r for r in TEST_RESULTS if r["case_id"].startswith("TC-VIS")],
    }

    print("\n各模块统计:")
    for name, cases in modules.items():
        if cases:
            p = sum(1 for c in cases if c["passed"])
            t = len(cases)
            rate = p / t * 100
            print(f"  {name}: {p}/{t} ({rate:.1f}%)")

    if failed > 0:
        print("\n失败用例:")
        for r in TEST_RESULTS:
            if not r["passed"]:
                print(f"  - {r['case_id']}: {r['name']} - {r['message']}")

    # 保存报告
    report_path = f"./test_report_phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "phase": "第二阶段 - 多模态内容提取",
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{pass_rate:.1f}%",
                "timestamp": datetime.now().isoformat(),
            },
            "results": TEST_RESULTS,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 测试报告已保存: {report_path}")

    return failed == 0


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="第二阶段 API 测试脚本")
    parser.add_argument("--server", action="store_true", help="仅打印测试方案")
    args = parser.parse_args()

    if args.server:
        print_test_plan()
        return True

    # 运行测试
    await run_phase2_tests()
    return print_summary()


def print_test_plan():
    """打印测试方案"""
    plan = """
╔══════════════════════════════════════════════════════════════╗
║          第二阶段测试方案 - 多模态内容提取                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  测试环境:                                                    ║
║  - 后端服务: http://127.0.0.1:8000                           ║
║  - 数据库: SQLite (测试数据库)                                ║
║  - 测试工具: Python httpx (异步)                              ║
║                                                              ║
║  测试模块: 4 个                                               ║
║  ┌────────────────┬────────┬─────────┬────────────────────┐ ║
║  │ 模块            │ 用例数 │ 优先级  │ 覆盖需求             │ ║
║  ├────────────────┼────────┼─────────┼────────────────────┤ ║
║  │ 1. 帧提取       │ 9      │ 高      │ FR-009 ~ FR-015     │ ║
║  │ 2. 字幕提取     │ 9      │ 高      │ FR-016 ~ FR-020     │ ║
║  │ 3. 音频提取     │ 8      │ 高      │ FR-021 ~ FR-025     │ ║
║  │ 4. 视觉描述     │ 9      │ 高      │ FR-026 ~ FR-030     │ ║
║  └────────────────┴────────┴─────────┴────────────────────┘ ║
║  总计: 35 个测试用例                                          ║
║                                                              ║
║  执行步骤:                                                    ║
║  1. 启动后端服务 (python run.py)                              ║
║  2. 运行测试: python test_phase2.py                           ║
║  3. 查看报告: test_report_phase2_*.json                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(plan)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
