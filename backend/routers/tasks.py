"""
任务管理API路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.models.task import (
    Task, TaskStatus, TaskType,
    TaskResponse, TaskListResponse
)
from backend.services.database import get_database

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def task_to_response(task: Task) -> TaskResponse:
    """将Task转换为API响应"""
    return TaskResponse(
        id=task.id,
        type=task.type,
        status=task.status,
        config=task.config,
        progress=task.progress,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        result=task.result
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选"),
    type: Optional[str] = Query(None, description="按类型筛选"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    列出所有任务

    支持按状态和类型筛选，支持分页。
    """
    db = get_database()

    # 转换枚举
    task_status = TaskStatus(status) if status else None
    task_type = TaskType(type) if type else None

    tasks = db.list_all(
        status=task_status,
        task_type=task_type,
        limit=limit,
        offset=offset
    )

    total = db.count(status=task_status, task_type=task_type)

    return TaskListResponse(
        tasks=[task_to_response(t) for t in tasks],
        total=total
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    获取任务详情
    """
    db = get_database()
    task = db.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_to_response(task)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务

    注意：运行中的任务需要先取消才能删除。
    """
    db = get_database()
    task = db.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status == TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="运行中的任务无法删除，请先取消")

    db.delete(task_id)

    return {"message": "任务已删除", "id": task_id}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    取消任务
    """
    from backend.services.download_service import get_download_service
    from backend.services.convert_service import get_convert_service
    from backend.services.upload_service import get_upload_service
    from backend.services.merge_service import get_merge_service

    db = get_database()
    task = db.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="只能取消运行中的任务")

    # 根据任务类型调用对应服务取消
    if task.type == TaskType.DOWNLOAD:
        success = get_download_service().cancel_task(task_id)
    elif task.type == TaskType.CONVERT:
        success = get_convert_service().cancel_task(task_id)
    elif task.type == TaskType.UPLOAD:
        success = get_upload_service().cancel_task(task_id)
    elif task.type == TaskType.MERGE:
        success = get_merge_service().cancel_task(task_id)
    else:
        raise HTTPException(status_code=400, detail=f"未知任务类型: {task.type}")

    if not success:
        raise HTTPException(status_code=500, detail="取消任务失败")

    return {"message": "任务已取消", "id": task_id}
