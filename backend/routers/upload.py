"""
上传API路由
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from backend.models.task import (
    CreateUploadTaskRequest,
    TaskResponse
)
from backend.services.upload_service import get_upload_service
from backend.routers.tasks import task_to_response

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/start", response_model=TaskResponse)
async def start_upload(request: CreateUploadTaskRequest):
    """
    创建并启动上传任务

    Args:
        request: 上传配置
            - local_dir: 本地LeRobot目录
            - bos_path: BOS目标路径
            - concurrency: 并发上传数（默认10）
            - include_videos: 是否包含视频文件
            - delete_after: 上传后是否删除本地文件
    """
    service = get_upload_service()

    # 检查mc工具
    ok, msg = service.check_mc()
    if not ok:
        raise HTTPException(status_code=500, detail=f"mc工具不可用: {msg}")

    # 创建任务
    task = service.create_task(request)

    # 启动任务
    if not service.start_task(task.id):
        raise HTTPException(status_code=500, detail="启动任务失败")

    # 重新获取任务（状态已更新）
    task = service.get_task(task.id)

    return task_to_response(task)


@router.get("/{task_id}/progress", response_model=TaskResponse)
async def get_upload_progress(task_id: str):
    """
    获取上传任务进度
    """
    service = get_upload_service()
    task = service.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_to_response(task)


@router.get("/scan-dirs")
async def scan_dirs(base_dir: str) -> List[Dict[str, Any]]:
    """
    扫描可上传的LeRobot目录

    返回指定目录下所有符合LeRobot格式的子目录列表。
    """
    service = get_upload_service()
    dirs = service.scan_dirs(base_dir)

    return dirs


@router.get("/scan-episodes")
async def scan_episodes(
    base_dir: str,
    include_thumbnails: bool = True
) -> List[Dict[str, Any]]:
    """
    扫描 LeRobot 目录，返回 episode 详情和 env 相机缩略图预览

    用于在上传前预览 episode 内容，让用户选择要上传的 episode。

    Args:
        base_dir: LeRobot 数据目录路径
        include_thumbnails: 是否包含缩略图（默认 True，设为 False 可加速响应）

    Returns:
        [{
            "name": "episode_0001",
            "path": "/path/to/episode_0001",
            "frame_count": 349,
            "size": 176000,
            "thumbnails": [
                "data:image/jpeg;base64,...",  # 第 1 帧
                "data:image/jpeg;base64,...",  # 第 1/3 帧
                "data:image/jpeg;base64,...",  # 第 2/3 帧
                "data:image/jpeg;base64,..."   # 最后 1 帧
            ]
        }]
    """
    service = get_upload_service()
    return service.scan_episodes(base_dir, include_thumbnails=include_thumbnails)
