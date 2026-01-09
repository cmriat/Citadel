"""
合并API路由
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException

from backend.models.task import CreateMergeTaskRequest, TaskResponse
from backend.services.merge_service import get_merge_service
from backend.routers.tasks import task_to_response

router = APIRouter(prefix="/api/merge", tags=["merge"])


@router.post("/start", response_model=TaskResponse)
async def start_merge(request: CreateMergeTaskRequest):
    """
    创建并启动合并任务

    将多个 LeRobot episode 合并为单个数据集。

    Args:
        request: 合并配置
            - source_dirs: 源 episode 目录列表
            - output_dir: 输出目录
            - state_max_dim: 状态向量最大维度（默认14）
            - action_max_dim: 动作向量最大维度（默认14）
            - fps: 视频帧率（默认25）
            - copy_images: 是否复制图像文件（默认False）
    """
    service = get_merge_service()

    # 验证参数
    if not request.source_dirs:
        raise HTTPException(status_code=400, detail="源目录列表不能为空")

    if not request.output_dir:
        raise HTTPException(status_code=400, detail="输出目录不能为空")

    # 验证源目录是否存在且为有效的 LeRobot 格式
    for src_dir in request.source_dirs:
        src_path = Path(src_dir)
        if not src_path.exists():
            raise HTTPException(status_code=400, detail=f"源目录不存在: {src_dir}")
        if not src_path.is_dir():
            raise HTTPException(status_code=400, detail=f"路径不是目录: {src_dir}")
        # 检查是否为有效的 LeRobot 格式（应有 meta/info.json）
        info_file = src_path / "meta" / "info.json"
        if not info_file.exists():
            raise HTTPException(
                status_code=400,
                detail=f"无效的 LeRobot 数据目录（缺少 meta/info.json）: {src_dir}"
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
async def get_merge_progress(task_id: str):
    """
    获取合并任务进度
    """
    service = get_merge_service()
    task = service.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_to_response(task)
