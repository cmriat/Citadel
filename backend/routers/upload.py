"""
上传API路由
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.models.task import CreateUploadTaskRequest, TaskResponse
from backend.services.upload_service import get_upload_service
from backend.routers.tasks import task_to_response

router = APIRouter(prefix="/api/upload", tags=["upload"])


# ============ QC Result Models ============


class QCResultRequest(BaseModel):
    """QC 结果保存请求"""

    base_dir: str
    passed: List[str]
    failed: List[str]

    # 用于多机协同：识别来源客户端，以及乐观锁/覆盖控制
    client_id: Optional[str] = None
    base_timestamp: Optional[str] = None
    force: bool = False


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
    base_dir: str, include_thumbnails: bool = True
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
async def get_video_stream(base_dir: str, episode_name: str, camera: str = "cam_env"):
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
            status_code=404, detail=f"视频文件不存在: {episode_name}/{camera}"
        )

    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"},
    )


# ============ QC Result Persistence / Broadcast ============

QC_RESULT_FILENAME = "qc_result.json"


class QCEpisodeUpdateRequest(BaseModel):
    """单个 episode 的 QC 状态更新请求（用于多机协同）"""

    base_dir: str
    episode_name: str
    status: Literal["passed", "failed", "pending"]

    client_id: Optional[str] = None
    base_timestamp: Optional[str] = None
    force: bool = False


class _QCWebSocketManager:
    """基于内存的 room 广播管理器（单实例部署可用）"""

    def __init__(self) -> None:
        self._rooms: Dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, dataset_key: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(dataset_key, set()).add(websocket)

    async def disconnect(self, dataset_key: str, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(dataset_key)
            if not room:
                return
            room.discard(websocket)
            if not room:
                self._rooms.pop(dataset_key, None)

    async def broadcast(self, dataset_key: str, message: Dict[str, Any]) -> None:
        async with self._lock:
            room = list(self._rooms.get(dataset_key, set()))

        if not room:
            return

        async def _send(ws: WebSocket) -> bool:
            try:
                await ws.send_json(message)
                return True
            except Exception:
                return False

        results = await asyncio.gather(*(_send(ws) for ws in room))
        dead = [ws for ws, ok in zip(room, results) if not ok]

        if dead:
            async with self._lock:
                current_room = self._rooms.get(dataset_key)
                if not current_room:
                    return
                for ws in dead:
                    current_room.discard(ws)
                if not current_room:
                    self._rooms.pop(dataset_key, None)


_qc_ws_manager = _QCWebSocketManager()

_qc_file_locks: Dict[str, asyncio.Lock] = {}
_qc_file_locks_guard = asyncio.Lock()


async def _get_qc_lock(dataset_key: str) -> asyncio.Lock:
    async with _qc_file_locks_guard:
        lock = _qc_file_locks.get(dataset_key)
        if lock is None:
            lock = asyncio.Lock()
            _qc_file_locks[dataset_key] = lock
        return lock


def _resolve_path(p: Path) -> Path:
    try:
        return p.resolve(strict=False)
    except Exception:
        return p.absolute()


def _get_qc_file_and_dataset_key(base_dir: str) -> tuple[Path, str]:
    """由 base_dir(lerobot 目录) 推导 qc_result.json 路径与房间 key。"""

    base_path = _resolve_path(Path(base_dir).expanduser())
    dataset_root = base_path.parent
    qc_file = dataset_root / QC_RESULT_FILENAME
    return qc_file, str(dataset_root)


def _load_qc_data(qc_file: Path) -> Optional[Dict[str, Any]]:
    if not qc_file.exists():
        return None

    with open(qc_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_qc_data_atomic(qc_file: Path, qc_data: Dict[str, Any]) -> None:
    tmp = qc_file.with_suffix(qc_file.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(qc_data, f, ensure_ascii=False, indent=2)
    tmp.replace(qc_file)


@router.websocket("/qc/ws")
async def qc_ws(websocket: WebSocket, base_dir: str, client_id: Optional[str] = None):
    """QC 质检结果的实时同步通道（按目录分房间）"""

    qc_file, dataset_key = _get_qc_file_and_dataset_key(base_dir)
    await _qc_ws_manager.connect(dataset_key, websocket)

    try:
        # 连接建立后回一条握手消息，便于前端调试
        current = _load_qc_data(qc_file) or {}
        await websocket.send_json(
            {
                "type": "qc_ws_connected",
                "dataset_key": dataset_key,
                "client_id": client_id,
                "timestamp": current.get("timestamp"),
            }
        )

        # 维持连接：前端可选发 ping，服务端回 pong
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await _qc_ws_manager.disconnect(dataset_key, websocket)


@router.post("/update-qc-episode")
async def update_qc_episode(request: QCEpisodeUpdateRequest) -> Dict[str, Any]:
    """更新单个 episode 的 QC 状态，并广播到同目录的所有客户端。"""

    try:
        qc_file, dataset_key = _get_qc_file_and_dataset_key(request.base_dir)
        lock = await _get_qc_lock(dataset_key)

        async with lock:
            existing = _load_qc_data(qc_file)
            current_ts = (existing or {}).get("timestamp")

            if existing and not request.force:
                conflict = (
                    request.base_timestamp is None
                    or current_ts is None
                    or request.base_timestamp != current_ts
                )
                if conflict:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "message": "已存在质检结果，请确认是否覆盖",
                            "current": {
                                "timestamp": current_ts,
                                "passed_count": len((existing or {}).get("passed", [])),
                                "failed_count": len((existing or {}).get("failed", [])),
                            },
                        },
                    )

            existing_data = existing or {}
            passed_set = set(existing_data.get("passed", []))
            failed_set = set(existing_data.get("failed", []))

            ep = request.episode_name
            passed_set.discard(ep)
            failed_set.discard(ep)

            if request.status == "passed":
                passed_set.add(ep)
            elif request.status == "failed":
                failed_set.add(ep)

            new_timestamp = datetime.now().isoformat()
            qc_data = {
                "passed": sorted(passed_set),
                "failed": sorted(failed_set),
                "timestamp": new_timestamp,
                "lerobot_dir": str(Path(request.base_dir)),
            }
            _write_qc_data_atomic(qc_file, qc_data)

        await _qc_ws_manager.broadcast(
            dataset_key,
            {
                "type": "qc_episode_updated",
                "dataset_key": dataset_key,
                "episode_name": request.episode_name,
                "status": request.status,
                "timestamp": new_timestamp,
                "source_client_id": request.client_id,
            },
        )

        return {
            "success": True,
            "dataset_key": dataset_key,
            "timestamp": new_timestamp,
            "passed_count": len(qc_data["passed"]),
            "failed_count": len(qc_data["failed"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 QC episode 失败: {str(e)}")


@router.post("/save-qc-result")
async def save_qc_result(request: QCResultRequest) -> Dict[str, Any]:
    """保存 QC 质检结果到数据目录，并广播到同目录的所有客户端。"""

    try:
        qc_file, dataset_key = _get_qc_file_and_dataset_key(request.base_dir)
        lock = await _get_qc_lock(dataset_key)

        async with lock:
            existing = _load_qc_data(qc_file)
            if existing and not request.force:
                current_ts = existing.get("timestamp")
                conflict = (
                    request.base_timestamp is None
                    or current_ts is None
                    or request.base_timestamp != current_ts
                )

                if conflict:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "message": "已存在质检结果，请确认是否覆盖",
                            "current": {
                                "timestamp": current_ts,
                                "passed_count": len(existing.get("passed", [])),
                                "failed_count": len(existing.get("failed", [])),
                            },
                        },
                    )

            passed_set = set(request.passed)
            failed_set = set(request.failed)
            passed_set -= failed_set

            new_timestamp = datetime.now().isoformat()
            qc_data = {
                "passed": sorted(passed_set),
                "failed": sorted(failed_set),
                "timestamp": new_timestamp,
                "lerobot_dir": str(Path(request.base_dir)),
            }
            _write_qc_data_atomic(qc_file, qc_data)

        await _qc_ws_manager.broadcast(
            dataset_key,
            {
                "type": "qc_result_updated",
                "dataset_key": dataset_key,
                "timestamp": new_timestamp,
                "source_client_id": request.client_id,
            },
        )

        return {
            "success": True,
            "dataset_key": dataset_key,
            "timestamp": new_timestamp,
            "file_path": str(qc_file),
            "passed_count": len(qc_data["passed"]),
            "failed_count": len(qc_data["failed"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存 QC 结果失败: {str(e)}")


@router.get("/load-qc-result", response_model=QCResultResponse)
async def load_qc_result(base_dir: str) -> QCResultResponse:
    """加载 QC 质检结果。"""

    try:
        qc_file, _dataset_key = _get_qc_file_and_dataset_key(base_dir)

        if not qc_file.exists():
            return QCResultResponse(passed=[], failed=[], exists=False)

        with open(qc_file, "r", encoding="utf-8") as f:
            qc_data = json.load(f)

        return QCResultResponse(
            passed=qc_data.get("passed", []),
            failed=qc_data.get("failed", []),
            timestamp=qc_data.get("timestamp"),
            exists=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载 QC 结果失败: {str(e)}")
