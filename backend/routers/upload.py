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
