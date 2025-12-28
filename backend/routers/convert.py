"""
转换API路由
"""

from typing import List
from fastapi import APIRouter, HTTPException

from backend.models.task import (
    CreateConvertTaskRequest,
    TaskResponse
)
from backend.services.convert_service import get_convert_service
from backend.routers.tasks import task_to_response

router = APIRouter(prefix="/api/convert", tags=["convert"])


@router.post("/start", response_model=TaskResponse)
async def start_convert(request: CreateConvertTaskRequest):
    """
    创建并启动转换任务

    Args:
        request: 转换配置
            - input_dir: 输入HDF5目录
            - output_dir: 输出LeRobot目录
            - robot_type: 机器人类型
            - fps: 视频帧率
            - task: 任务描述
            - parallel_jobs: 并发转换数
            - file_pattern: 文件匹配模式
    """
    service = get_convert_service()

    # 扫描文件
    files = service.scan_files(request.input_dir, request.file_pattern)
    if not files:
        raise HTTPException(
            status_code=400,
            detail=f"输入目录中未找到匹配 '{request.file_pattern}' 的文件"
        )

    # 创建任务
    task = service.create_task(request)

    # 启动任务
    if not service.start_task(task.id):
        raise HTTPException(status_code=500, detail="启动任务失败")

    # 重新获取任务（状态已更新）
    task = service.get_task(task.id)

    return task_to_response(task)


@router.get("/{task_id}/progress", response_model=TaskResponse)
async def get_convert_progress(task_id: str):
    """
    获取转换任务进度
    """
    service = get_convert_service()
    task = service.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_to_response(task)


@router.get("/scan-files")
async def scan_files(
    input_dir: str,
    file_pattern: str = "episode_*.h5"
) -> List[str]:
    """
    扫描目录中的HDF5文件

    用于在创建转换任务前预览将要转换的文件列表。
    """
    service = get_convert_service()
    files = service.scan_files(input_dir, file_pattern)

    return files
