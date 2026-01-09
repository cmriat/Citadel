"""
下载API路由
"""

from fastapi import APIRouter, HTTPException

from backend.models.task import (
    CreateDownloadTaskRequest,
    TaskResponse
)
from backend.services.download_service import get_download_service
from backend.routers.tasks import task_to_response

router = APIRouter(prefix="/api/download", tags=["download"])


@router.post("/start", response_model=TaskResponse)
async def start_download(request: CreateDownloadTaskRequest):
    """
    创建并启动下载任务

    Args:
        request: 下载配置
            - bos_path: BOS远程路径
            - local_path: 本地保存路径
            - concurrency: 并发下载数（默认10）
            - mc_path: mc可执行文件路径
    """
    service = get_download_service()

    # 检查mc工具
    ok, msg = service.check_mc()
    if not ok:
        raise HTTPException(status_code=500, detail=f"mc工具不可用: {msg}")

    # 检查BOS连接
    ok, msg = service.check_connection()
    if not ok:
        raise HTTPException(status_code=500, detail=f"BOS连接失败: {msg}")

    # 创建任务
    task = service.create_task(request)

    # 启动任务
    if not service.start_task(task.id):
        raise HTTPException(status_code=500, detail="启动任务失败")

    # 重新获取任务（状态已更新）
    task = service.get_task(task.id)
    if not task:
        raise HTTPException(status_code=500, detail="任务创建后无法获取")

    return task_to_response(task)


@router.get("/{task_id}/progress", response_model=TaskResponse)
async def get_download_progress(task_id: str):
    """
    获取下载任务进度
    """
    service = get_download_service()
    task = service.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_to_response(task)


@router.get("/check-connection")
async def check_connection():
    """
    检查BOS连接状态
    """
    service = get_download_service()

    # 检查mc工具
    mc_ok, mc_msg = service.check_mc()
    if not mc_ok:
        return {
            "connected": False,
            "mc_available": False,
            "error": mc_msg
        }

    # 检查BOS连接
    bos_ok, bos_msg = service.check_connection()

    return {
        "connected": bos_ok,
        "mc_available": True,
        "mc_version": mc_msg if mc_ok else None,
        "error": bos_msg if not bos_ok else None
    }


@router.get("/scan-bos")
async def scan_bos(bos_path: str):
    """
    扫描BOS路径下的HDF5文件

    用于在下载前检查远程路径是否存在可下载的文件。

    Args:
        bos_path: BOS路径 (如 bos:/citadel-bos/raw_data/)

    Returns:
        {
            "ready": bool,
            "file_count": int,
            "files": list[str],
            "error": str | None
        }
    """
    service = get_download_service()

    # 先检查mc工具
    mc_ok, mc_msg = service.check_mc()
    if not mc_ok:
        return {
            "ready": False,
            "file_count": 0,
            "files": [],
            "error": f"mc tool unavailable: {mc_msg}"
        }

    # 扫描BOS路径
    return service.scan_bos(bos_path)
