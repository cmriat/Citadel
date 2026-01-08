"""
上传API路由
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.models.task import (
    CreateUploadTaskRequest,
    TaskResponse
)
from backend.services.upload_service import get_upload_service
from backend.routers.tasks import task_to_response

router = APIRouter(prefix="/api/upload", tags=["upload"])


# ============ QC Result Models ============

class QCResultRequest(BaseModel):
    """QC 结果保存请求"""
    base_dir: str
    passed: List[str]
    failed: List[str]


class QCResultResponse(BaseModel):
    """QC 结果响应"""
    passed: List[str]
    failed: List[str]
    timestamp: Optional[str] = None
    exists: bool = True


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


@router.get("/video-stream")
async def get_video_stream(
    base_dir: str,
    episode_name: str,
    camera: str = "cam_env"
):
    """
    获取 episode 的视频流用于播放

    用于 QC 质检时播放 episode 视频。

    Args:
        base_dir: LeRobot 数据目录
        episode_name: episode 名称，如 "episode_0001"
        camera: 相机名称，默认 "cam_env"

    Returns:
        视频文件流（支持 Range 请求，便于视频 seek）
    """
    service = get_upload_service()
    video_path = service.get_video_path(base_dir, episode_name, camera)

    if not video_path:
        raise HTTPException(
            status_code=404,
            detail=f"视频文件不存在: {episode_name}/{camera}"
        )

    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600"
        }
    )


# ============ QC Result Persistence ============

QC_RESULT_FILENAME = "qc_result.json"


@router.post("/save-qc-result")
async def save_qc_result(request: QCResultRequest) -> Dict[str, Any]:
    """
    保存 QC 质检结果到数据目录

    将 QC 结果保存为 JSON 文件，放在 base_dir 同级目录下。
    例如：如果 base_dir 是 /data/lerobot，则保存到 /data/qc_result.json

    Args:
        request: QC 结果
            - base_dir: LeRobot 数据目录
            - passed: 通过的 episode 列表
            - failed: 不通过的 episode 列表

    Returns:
        保存结果信息
    """
    try:
        # base_dir 是 lerobot 目录，保存到其父目录
        base_path = Path(request.base_dir)
        parent_dir = base_path.parent
        qc_file = parent_dir / QC_RESULT_FILENAME

        qc_data = {
            "passed": request.passed,
            "failed": request.failed,
            "timestamp": datetime.now().isoformat(),
            "lerobot_dir": str(base_path)
        }

        with open(qc_file, "w", encoding="utf-8") as f:
            json.dump(qc_data, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "file_path": str(qc_file),
            "passed_count": len(request.passed),
            "failed_count": len(request.failed)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存 QC 结果失败: {str(e)}")


@router.get("/load-qc-result", response_model=QCResultResponse)
async def load_qc_result(base_dir: str) -> QCResultResponse:
    """
    加载 QC 质检结果

    从数据目录加载之前保存的 QC 结果。

    Args:
        base_dir: LeRobot 数据目录

    Returns:
        QC 结果（如果不存在则返回空结果）
    """
    try:
        base_path = Path(base_dir)
        parent_dir = base_path.parent
        qc_file = parent_dir / QC_RESULT_FILENAME

        if not qc_file.exists():
            return QCResultResponse(
                passed=[],
                failed=[],
                exists=False
            )

        with open(qc_file, "r", encoding="utf-8") as f:
            qc_data = json.load(f)

        return QCResultResponse(
            passed=qc_data.get("passed", []),
            failed=qc_data.get("failed", []),
            timestamp=qc_data.get("timestamp"),
            exists=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载 QC 结果失败: {str(e)}")
