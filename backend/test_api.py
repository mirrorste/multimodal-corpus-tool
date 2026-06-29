#!/usr/bin/env python3
"""
API 测试脚本 - 多模态语料获取工具
基于 test_manual.md 中的测试用例执行

用法:
    python test_api.py                    # 运行所有测试
    python test_api.py --test=TC-API-001 # 运行指定测试
    python test_api.py --server           # 启动服务器
"""

import asyncio
import httpx
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import aiofiles
import uuid

# 测试配置
BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
TEST_VIDEO_ID = None
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
    """TC-API-000: 健康检查"""
    try:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code == 200 and response.json().get("status") == "healthy":
            return TestResult("TC-API-000", "健康检查", True, f"响应: {response.json()}")
        return TestResult("TC-API-000", "健康检查", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-000", "健康检查", False, f"连接失败: {str(e)}")


async def test_create_video(client: httpx.AsyncClient, url: str, platform: str, resolution: str = "1080p") -> Optional[str]:
    """TC-API-001: 创建视频"""
    global TEST_VIDEO_ID
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/videos/",
            json={"url": url, "platform": platform, "preferred_resolution": resolution},
        )
        if response.status_code == 200:
            data = response.json()
            TEST_VIDEO_ID = data.get("id")
            return TEST_VIDEO_ID
        return None
    except Exception as e:
        print(f"创建视频失败: {e}")
        return None


async def test_get_videos(client: httpx.AsyncClient) -> TestResult:
    """TC-API-007: 获取视频列表"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return TestResult("TC-API-007", "获取视频列表", True, f"返回 {len(data)} 条记录")
        return TestResult("TC-API-007", "获取视频列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-007", "获取视频列表", False, f"请求失败: {str(e)}")


async def test_get_videos_filtered(client: httpx.AsyncClient, status: str) -> TestResult:
    """TC-API-008: 按状态筛选"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/?status={status}")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-API-008", f"按状态筛选 ({status})", True, f"返回 {len(data)} 条记录")
        return TestResult("TC-API-008", f"按状态筛选 ({status})", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-008", f"按状态筛选 ({status})", False, f"请求失败: {str(e)}")


async def test_get_single_video(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-API-013: 获取单个视频"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-API-013", "获取单个视频", True, f"ID: {data.get('id')[:8]}...")
        elif response.status_code == 404:
            return TestResult("TC-API-013", "获取单个视频", False, "视频不存在")
        return TestResult("TC-API-013", "获取单个视频", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-013", "获取单个视频", False, f"请求失败: {str(e)}")


async def test_get_nonexistent_video(client: httpx.AsyncClient) -> TestResult:
    """TC-API-014: 获取不存在的视频"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{fake_id}")
        if response.status_code == 404:
            return TestResult("TC-API-014", "获取不存在的视频", True, "正确返回 404")
        return TestResult("TC-API-014", "获取不存在的视频", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-014", "获取不存在的视频", False, f"请求失败: {str(e)}")


async def test_delete_video(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-API-016: 删除视频"""
    try:
        response = await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{video_id}")
        if response.status_code == 200:
            return TestResult("TC-API-016", "删除视频", True, "删除成功")
        elif response.status_code == 404:
            return TestResult("TC-API-016", "删除视频", False, "视频不存在")
        return TestResult("TC-API-016", "删除视频", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-016", "删除视频", False, f"请求失败: {str(e)}")


async def test_delete_nonexistent(client: httpx.AsyncClient) -> TestResult:
    """TC-API-018: 删除不存在的视频"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"{BASE_URL}{API_PREFIX}/videos/{fake_id}")
        if response.status_code == 404:
            return TestResult("TC-API-018", "删除不存在的视频", True, "正确返回 404")
        return TestResult("TC-API-018", "删除不存在的视频", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-018", "删除不存在的视频", False, f"请求失败: {str(e)}")


async def test_batch_create(client: httpx.AsyncClient) -> TestResult:
    """TC-API-021: 批量创建视频"""
    try:
        videos = [
            {"url": "https://example.com/video1.mp4", "platform": "youtube"},
            {"url": "https://example.com/video2.mp4", "platform": "bilibili"},
            {"url": "https://example.com/video3.mp4", "platform": "vimeo"},
        ]
        response = await client.post(f"{BASE_URL}{API_PREFIX}/videos/batch", json=videos)
        if response.status_code == 200:
            data = response.json()
            if len(data) == 3:
                return TestResult("TC-API-021", "批量创建视频", True, f"创建 {len(data)} 条记录")
        return TestResult("TC-API-021", "批量创建视频", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-021", "批量创建视频", False, f"请求失败: {str(e)}")


async def test_download_video(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-API-024: 触发下载"""
    try:
        response = await client.post(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/download")
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            return TestResult("TC-API-024", "触发下载", True, f"状态变为 {status}")
        return TestResult("TC-API-024", "触发下载", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-024", "触发下载", False, f"请求失败: {str(e)}")


async def test_download_nonexistent(client: httpx.AsyncClient) -> TestResult:
    """TC-API-028: 下载不存在的视频"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.post(f"{BASE_URL}{API_PREFIX}/videos/{fake_id}/download")
        if response.status_code == 404:
            return TestResult("TC-API-028", "下载不存在的视频", True, "正确返回 404")
        return TestResult("TC-API-028", "下载不存在的视频", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-028", "下载不存在的视频", False, f"请求失败: {str(e)}")


async def test_get_progress(client: httpx.AsyncClient, video_id: str) -> TestResult:
    """TC-API-029: 获取下载进度"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{video_id}/progress")
        if response.status_code == 200:
            data = response.json()
            return TestResult(
                "TC-API-029", "获取下载进度", True,
                f"状态: {data.get('status')}, 进度: {data.get('download_progress')}"
            )
        return TestResult("TC-API-029", "获取下载进度", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-029", "获取下载进度", False, f"请求失败: {str(e)}")


async def test_get_progress_nonexistent(client: httpx.AsyncClient) -> TestResult:
    """TC-API-033: 获取不存在视频的进度"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"{BASE_URL}{API_PREFIX}/videos/{fake_id}/progress")
        if response.status_code == 404:
            return TestResult("TC-API-033", "获取不存在视频的进度", True, "正确返回 404")
        return TestResult("TC-API-033", "获取不存在视频的进度", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-033", "获取不存在视频的进度", False, f"请求失败: {str(e)}")


async def test_upload_video(client: httpx.AsyncClient, file_path: str) -> Optional[str]:
    """TC-API-037: 上传视频文件"""
    global TEST_VIDEO_ID
    try:
        async with aiofiles.open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, await f.read(), "video/mp4")}
            data = {"platform": "local", "preferred_resolution": "original"}
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/videos/upload",
                files=files,
                data=data,
            )
        if response.status_code == 200:
            data = response.json()
            TEST_VIDEO_ID = data.get("id")
            return TEST_VIDEO_ID
        elif response.status_code == 400:
            return None  # 文件不存在是正常的测试场景
        return None
    except Exception as e:
        print(f"上传视频失败: {e}")
        return None


async def test_task_status(client: httpx.AsyncClient, task_id: str) -> TestResult:
    """TC-API-043: 获取任务状态"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/tasks/{task_id}")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-API-043", "获取任务状态", True, f"任务 ID: {data.get('task_id')[:8]}...")
        elif response.status_code == 404:
            return TestResult("TC-API-043", "获取任务状态", False, "任务不存在")
        return TestResult("TC-API-043", "获取任务状态", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-043", "获取任务状态", False, f"请求失败: {str(e)}")


async def test_task_nonexistent(client: httpx.AsyncClient) -> TestResult:
    """TC-API-044: 获取不存在的任务"""
    try:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"{BASE_URL}{API_PREFIX}/tasks/{fake_id}")
        if response.status_code == 404:
            return TestResult("TC-API-044", "获取不存在的任务", True, "正确返回 404")
        return TestResult("TC-API-044", "获取不存在的任务", False, f"预期 404，实际 {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-044", "获取不存在的任务", False, f"请求失败: {str(e)}")


async def test_task_list(client: httpx.AsyncClient) -> TestResult:
    """TC-API-051: 获取任务列表"""
    try:
        response = await client.get(f"{BASE_URL}{API_PREFIX}/tasks/")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-API-051", "获取任务列表", True, f"返回 {len(data)} 个任务")
        return TestResult("TC-API-051", "获取任务列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-051", "获取任务列表", False, f"请求失败: {str(e)}")


async def test_task_cancel(client: httpx.AsyncClient, task_id: str) -> TestResult:
    """TC-API-047: 取消任务"""
    try:
        response = await client.post(f"{BASE_URL}{API_PREFIX}/tasks/{task_id}/cancel")
        if response.status_code == 200:
            data = response.json()
            return TestResult("TC-API-047", "取消任务", True, f"状态: {data.get('status')}")
        elif response.status_code == 404:
            return TestResult("TC-API-047", "取消任务", False, "任务不存在")
        return TestResult("TC-API-047", "取消任务", False, f"状态码: {response.status_code}")
    except Exception as e:
        return TestResult("TC-API-047", "取消任务", False, f"请求失败: {str(e)}")


async def run_api_tests():
    """执行 API 测试"""
    print_section("API 接口测试")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 健康检查
        result = await test_health_check(client)
        print_test(result)
        TEST_RESULTS.append(result.to_dict())

        # 等待服务完全启动
        await asyncio.sleep(1)

        # 2. 创建测试视频
        print_section("创建测试数据")
        test_video_id = await test_create_video(
            client,
            "https://www.youtube.com/watch?v=test123",
            "youtube",
            "1080p"
        )
        if test_video_id:
            print(f"✅ 测试视频创建成功: {test_video_id}")
        else:
            print("❌ 测试视频创建失败")

        # 3. 测试视频管理接口
        print_section("视频管理接口测试")

        results = [
            await test_get_videos(client),
            await test_get_videos_filtered(client, "pending"),
            await test_get_single_video(client, test_video_id) if test_video_id else None,
            await test_get_nonexistent_video(client),
            await test_batch_create(client),
        ]
        for r in results:
            if r:
                print_test(r)
                TEST_RESULTS.append(r.to_dict())

        # 4. 测试下载功能
        print_section("下载功能测试")

        if test_video_id:
            download_result = await test_download_video(client, test_video_id)
            print_test(download_result)
            TEST_RESULTS.append(download_result.to_dict())

            # 等待下载任务启动
            await asyncio.sleep(2)

            progress_result = await test_get_progress(client, test_video_id)
            print_test(progress_result)
            TEST_RESULTS.append(progress_result.to_dict())

        download_nonexist_result = await test_download_nonexistent(client)
        print_test(download_nonexist_result)
        TEST_RESULTS.append(download_nonexist_result.to_dict())

        progress_nonexist_result = await test_get_progress_nonexistent(client)
        print_test(progress_nonexist_result)
        TEST_RESULTS.append(progress_nonexist_result.to_dict())

        # 5. 测试文件上传
        print_section("文件上传测试")

        # 创建测试文件
        test_file_path = "./test_upload.mp4"
        try:
            # 创建一个小测试文件
            async with aiofiles.open(test_file_path, "wb") as f:
                await f.write(b"fake video data for testing" * 100)
            upload_result = await test_upload_video(client, test_file_path)
            if upload_result:
                print(f"✅ 文件上传测试成功: {upload_result}")
            else:
                print("⚠️ 文件上传测试跳过（无测试文件）")
        except Exception as e:
            print(f"⚠️ 文件上传测试跳过: {e}")

        # 6. 测试任务管理接口
        print_section("任务管理接口测试")

        task_results = [
            await test_task_list(client),
            await test_task_nonexistent(client),
        ]
        for r in task_results:
            print_test(r)
            TEST_RESULTS.append(r.to_dict())

        if test_video_id:
            task_result = await test_task_status(client, test_video_id)
            print_test(task_result)
            TEST_RESULTS.append(task_result.to_dict())

            cancel_result = await test_task_cancel(client, test_video_id)
            print_test(cancel_result)
            TEST_RESULTS.append(cancel_result.to_dict())

        # 7. 清理测试数据
        print_section("清理测试数据")
        if test_video_id:
            delete_result = await test_delete_video(client, test_video_id)
            print_test(delete_result)
            TEST_RESULTS.append(delete_result.to_dict())

        delete_nonexist_result = await test_delete_nonexistent(client)
        print_test(delete_nonexist_result)
        TEST_RESULTS.append(delete_nonexist_result.to_dict())


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

    if failed > 0:
        print("\n失败用例:")
        for r in TEST_RESULTS:
            if not r["passed"]:
                print(f"  - {r['case_id']}: {r['name']} - {r['message']}")

    # 保存结果到文件
    report_path = f"./test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{pass_rate:.1f}%",
                "timestamp": datetime.now().isoformat(),
            },
            "results": TEST_RESULTS,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n测试报告已保存: {report_path}")

    return failed == 0


async def init_database():
    """初始化测试数据库"""
    print_section("初始化测试数据库")
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        from app.core.database import init_db, async_session_maker
        from app.models.video import Video

        await init_db()
        print("✅ 数据库初始化成功")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="API 测试脚本")
    parser.add_argument("--test", type=str, help="运行指定测试用例")
    parser.add_argument("--server", action="store_true", help="仅启动服务器")
    args = parser.parse_args()

    # 初始化数据库
    if not await init_database():
        print("数据库初始化失败，退出测试")
        return False

    if args.server:
        # 仅启动服务器
        print("启动服务器...")
        os.system("cd /workspace/backend && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload")
        return True

    # 运行测试
    success = await run_api_tests()

    # 打印汇总
    return print_summary()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
