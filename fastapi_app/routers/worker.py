"""Worker 控制 API"""

import logging
from fastapi import APIRouter, HTTPException

from ..schemas.models import (
    WorkerStartRequest, WorkerStatus, ApiResponse
)
from ..services.worker_service import worker_service
from .config import get_current_config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start", response_model=ApiResponse)
async def start_workers(request: WorkerStartRequest):
    """启动 Workers"""
    config = get_current_config()

    # 验证配置
    if not config.bos.access_key or not config.bos.secret_key:
        raise HTTPException(status_code=400, detail="请先配置 BOS 凭证")

    if not config.paths.raw_data:
        raise HTTPException(status_code=400, detail="请先配置原始数据路径")

    # 设置配置
    worker_service.set_config(config.model_dump())

    # 启动 workers
    success = worker_service.start(num_workers=request.num_workers)

    if success:
        return ApiResponse(success=True, message=f"已启动 {request.num_workers} 个 Worker")
    else:
        return ApiResponse(success=False, message="Workers 已在运行中")


@router.post("/stop", response_model=ApiResponse)
async def stop_workers():
    """停止 Workers"""
    success = worker_service.stop()

    if success:
        return ApiResponse(success=True, message="Workers 已停止")
    else:
        return ApiResponse(success=False, message="Workers 未在运行")


@router.get("/status", response_model=WorkerStatus)
async def get_worker_status():
    """获取 Worker 状态"""
    status = worker_service.get_status()
    return WorkerStatus(**status)
