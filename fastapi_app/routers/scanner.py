"""Scanner 控制 API"""

import logging
from fastapi import APIRouter, HTTPException

from ..schemas.models import (
    ScannerStartRequest, ScannerStatus, ApiResponse, ScanMode
)
from ..services.scanner_service import scanner_service
from .config import get_current_config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start", response_model=ApiResponse)
async def start_scanner(request: ScannerStartRequest):
    """启动扫描器"""
    config = get_current_config()

    # 验证配置
    if not config.bos.access_key or not config.bos.secret_key:
        raise HTTPException(status_code=400, detail="请先配置 BOS 凭证")

    if not config.paths.raw_data:
        raise HTTPException(status_code=400, detail="请先配置原始数据路径")

    # 设置配置
    scanner_service.set_config(config.model_dump())

    # 判断是否全量扫描
    full_scan = request.mode == ScanMode.ONCE

    # 启动扫描
    success = scanner_service.start(
        mode=request.mode.value,
        interval=request.interval,
        full_scan=full_scan
    )

    if success:
        mode_text = "持续扫描" if request.mode == ScanMode.CONTINUOUS else "全量扫描"
        return ApiResponse(success=True, message=f"{mode_text}已启动")
    else:
        return ApiResponse(success=False, message="扫描器已在运行中")


@router.post("/stop", response_model=ApiResponse)
async def stop_scanner():
    """停止扫描器"""
    success = scanner_service.stop()

    if success:
        return ApiResponse(success=True, message="扫描器已停止")
    else:
        return ApiResponse(success=False, message="扫描器未在运行")


@router.get("/status", response_model=ScannerStatus)
async def get_scanner_status():
    """获取扫描器状态"""
    status = scanner_service.get_status()
    return ScannerStatus(**status)
