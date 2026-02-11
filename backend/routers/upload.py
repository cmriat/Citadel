"""
上传API路由
"""

import asyncio
import json
import logging
from email.utils import parsedate
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from backend.models.task import CreateUploadTaskRequest, TaskResponse
from backend.services.upload_service import get_upload_service
from backend.routers.tasks import task_to_response

from backend.services.postgre_sql_manager import PostgreSqlManager

router = APIRouter(prefix="/api/upload", tags=["upload"])

logger = logging.getLogger(__name__)
# Uvicorn 默认 logging config 只配置了 uvicorn.* logger。
# 为了让我们自己的 INFO 日志在 dev/start 启动方式下也能直接出现在控制台，
# 对关键诊断日志使用 uvicorn.error 这个已配置 handler 的 logger。
_uvicorn_logger = logging.getLogger("uvicorn.error")


_NOT_MODIFIED_HEADERS = {
    # 与 Starlette NotModifiedResponse 行为对齐（仅保留缓存相关 header）
    "cache-control",
    "content-location",
    "date",
    "etag",
    "expires",
    "vary",
}


def _is_not_modified(etag: str, last_modified: str, request: Request) -> bool:
    """判断请求是否可用 304 Not Modified。"""

    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        if if_none_match.strip() == "*":
            return True

        # 兼容 `W/"..."` 形式
        for part in if_none_match.split(","):
            tag = part.strip()
            if tag.startswith("W/"):
                tag = tag[2:].strip()
            if tag == etag:
                return True
        return False

    if_modified_since = request.headers.get("if-modified-since")
    if if_modified_since:
        ims = parsedate(if_modified_since)
        lm = parsedate(last_modified)
        if ims is not None and lm is not None and ims >= lm:
            return True

    return False


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
async def get_video_stream(
    request: Request, base_dir: str, episode_name: str, camera: str = "cam_env"
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
            status_code=404, detail=f"视频文件不存在: {episode_name}/{camera}"
        )

    stat_result = Path(video_path).stat()
    resp = FileResponse(
        video_path,
        media_type="video/mp4",
        stat_result=stat_result,
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=3600"},
    )

    # 对非 Range 请求支持 304，让浏览器重复打开同一视频时尽量复用缓存。
    if request.headers.get("range") is None:
        etag = resp.headers.get("etag")
        last_modified = resp.headers.get("last-modified")
        if etag and last_modified and _is_not_modified(etag, last_modified, request):
            headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower() in _NOT_MODIFIED_HEADERS
            }
            return Response(status_code=304, headers=headers)

    return resp


# ============ QC Result Persistence / Broadcast ============

QC_RESULT_FILENAME = "qc_result.json"


class QCEpisodeUpdateRequest(BaseModel):
    """单个 episode 的 QC 状态更新请求（用于多机协同）"""

    base_dir: str
    episode_name: str
    status: Literal["passed", "failed", "pending"]

    # 细粒度乐观锁：仅检测同一 episode 的并发修改。
    # 传入你“看到的旧状态”，服务端仅在该 episode 状态已变化时返回 409。
    base_status: Optional[Literal["passed", "failed", "pending"]] = None

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
    # base_dir 可能是：
    # - dataset_root/lerobot（历史约定）
    # - dataset_root（episode 平铺在根目录时）
    dataset_root = PostgreSqlManager.resolve_dataset_root_from_base_dir(base_path)
    qc_file = dataset_root / QC_RESULT_FILENAME
    return qc_file, str(dataset_root)


def _load_qc_data(qc_file: Path) -> Optional[Dict[str, Any]]:
    if not qc_file.exists():
        return None

    with open(qc_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_episode_status(
    qc_data: Dict[str, Any], episode_name: str
) -> Literal["passed", "failed", "pending"]:
    passed = set(qc_data.get("passed", []) or [])
    failed = set(qc_data.get("failed", []) or [])
    if episode_name in passed:
        return "passed"
    if episode_name in failed:
        return "failed"
    return "pending"


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
            existing_data = existing or {}
            current_ts = existing_data.get("timestamp")

            if existing and not request.force:
                conflict_payload: Optional[Dict[str, Any]] = None

                # 新版：按 episode 粒度做冲突检测，避免不同 episode 互相干扰。
                if request.base_status is not None:
                    current_status = _get_episode_status(
                        existing_data, request.episode_name
                    )
                    if request.base_status != current_status:
                        conflict_payload = {
                            "message": "该 episode 已被其他人更新，请确认是否覆盖",
                            "conflict_type": "episode",
                            "episode": {
                                "name": request.episode_name,
                                "current_status": current_status,
                                "requested_status": request.status,
                                "base_status": request.base_status,
                            },
                        }
                else:
                    # 旧版：全局 timestamp 乐观锁（保留兼容旧前端）。
                    conflict = (
                        request.base_timestamp is None
                        or current_ts is None
                        or request.base_timestamp != current_ts
                    )
                    if conflict:
                        conflict_payload = {
                            "message": "已存在质检结果，请确认是否覆盖",
                            "conflict_type": "timestamp",
                        }

                if conflict_payload is not None:
                    conflict_payload["current"] = {
                        "timestamp": current_ts,
                        "passed_count": len(existing_data.get("passed", []) or []),
                        "failed_count": len(existing_data.get("failed", []) or []),
                    }
                    return JSONResponse(status_code=409, content=conflict_payload)

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


# ============ QC Result -> Postgres Sync (dwd_episode) ============


class QCSyncToDbRequest(BaseModel):
    """将 QC 结果同步到 Postgres dwd_episode。

    注意：为了避免误写库，默认 dry_run=True，仅返回将要执行的 SQL。

    字段语义（与数仓约定对齐）：
    - validity: is_valid=1 表示通过，0 表示不通过
    - manual: quality_problem_manual=1 表示有问题（不通过），0 表示无问题（通过）
    """

    base_dir: str
    passed: List[str] = []
    failed: List[str] = []

    # a) none: 不写库
    # b) validity: 写入 is_valid
    # c) manual: 写入 quality_problem_manual
    mode: Literal["none", "validity", "manual"]
    dry_run: bool = True

    # 可选：在生成 UPDATE 语句前先校验目标记录是否存在。
    # - 若缺失，将跳过这些记录，并在响应中返回缺失列表（前端可提示原因）。
    check_exists: bool = False

    # 若路径不符合规范，可手动覆盖这 3 个字段
    device_id: Optional[str] = None
    collect_date: Optional[str] = None
    task_name: Optional[str] = None


@router.post("/sync-qc-to-db")
async def sync_qc_to_db(request: QCSyncToDbRequest) -> Dict[str, Any]:
    """QC 确认后可选同步质检结果到 Postgres(dwd_episode)。

    - 通过路径+相关信息定位 dwd_episode.id（默认按 UUID v5 规则计算，不依赖 DB 查询）
    - 按主键 id 更新字段：
      - validity: is_valid=1/0
      - manual: quality_problem_manual=1(有问题)/0(无问题)
    """

    if request.mode == "none":
        return {
            "success": True,
            "dry_run": True,
            "mode": request.mode,
            "statements": [],
            "statement_count": 0,
            "episode_count": 0,
            "episode_update_count": 0,
        }

    # 同一条 episode 在数仓里可能同时存在两条记录：
    # - generated_from=format_conversion + data_format=lerobot（LeRobot 转换结果）
    # - generated_from=collect + data_format=h5（原始采集 H5）
    # 因此同步 QC 时默认同时更新两者。
    _target_sources = (
        ("format_conversion", "lerobot"),
        ("collect", "h5"),
    )

    def _compute_episode_id_items() -> List[Dict[str, str]]:
        """计算需校验存在性的 dwd_episode.id 列表（包含多种 generated_from）。"""

        dataset_root = PostgreSqlManager.resolve_dataset_root_from_base_dir(
            request.base_dir
        )

        device_id = request.device_id
        collect_date = request.collect_date
        task_name = request.task_name
        if device_id is None or collect_date is None or task_name is None:
            parsed = PostgreSqlManager.parse_pfs_lerobot_dataset_root(dataset_root)
            device_id = device_id or parsed["device_id"]
            collect_date = collect_date or parsed["collect_date"]
            task_name = task_name or parsed["task_name"]

        assert device_id is not None
        assert collect_date is not None
        assert task_name is not None

        passed_set = set(request.passed or [])
        failed_set = set(request.failed or [])
        passed_set -= failed_set

        episode_names = sorted(passed_set | failed_set)
        items: List[Dict[str, str]] = []
        for ep_name in episode_names:
            ep_idx = PostgreSqlManager.parse_episode_index(ep_name)
            for generated_from, data_format in _target_sources:
                episode_id = PostgreSqlManager.compute_dwd_episode_id(
                    device_id=device_id,
                    collect_date=collect_date,
                    task_name=task_name,
                    episode_index=ep_idx,
                    generated_from=generated_from,
                    data_format=data_format,
                )
                items.append(
                    {
                        "episode_name": ep_name,
                        "generated_from": generated_from,
                        "data_format": data_format,
                        "id": episode_id,
                    }
                )
        return items

    def _check_dwd_episode_exists(
        episode_id_items: List[Dict[str, str]],
        qc_col: str,
    ) -> tuple[set[str], List[Dict[str, str]], Dict[str, Any]]:
        ids = sorted({it["id"] for it in episode_id_items})
        if not ids:
            return set(), [], {}

        try:
            db = PostgreSqlManager()
        except Exception as e:
            # 连接/驱动缺失等问题：返回可读原因。
            raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")

        try:
            # 批量查询存在的 id。
            # 使用 uuid[] 显式 cast，避免 array 类型不明确导致的适配问题。
            db.cursor.execute(
                f"SELECT id::text, {qc_col} FROM dwd_episode WHERE id = ANY(%s::uuid[]);",
                (ids,),
            )
            rows = db.cursor.fetchall()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"数据库查询失败: {str(e)}")
        finally:
            try:
                db.close()
            except Exception:
                pass

        existing_ids = {str(r[0]) for r in rows}
        non_null_values = {
            str(r[0]): r[1] for r in rows if len(r) >= 2 and r[1] is not None
        }
        missing = [it for it in episode_id_items if it["id"] not in existing_ids]
        return existing_ids, missing, non_null_values

    try:
        exists_check = None
        existing_ids: Optional[set[str]] = None
        passed_set = set(request.passed or [])
        failed_set = set(request.failed or [])
        passed_set -= failed_set
        episode_names = sorted(passed_set | failed_set)
        episode_count = len(episode_names)
        episode_update_count = episode_count
        if request.check_exists:
            qc_col = (
                "is_valid" if request.mode == "validity" else "quality_problem_manual"
            )
            episode_id_items = _compute_episode_id_items()
            existing_ids, missing, non_null_values = _check_dwd_episode_exists(
                episode_id_items, qc_col
            )

            # 以 episode 维度统计：只要任一数据源存在，就认为该 episode 会被更新。
            episodes_to_update = {
                it["episode_name"]
                for it in episode_id_items
                if it["id"] in existing_ids
            }
            episode_update_count = len(episodes_to_update)

            # 覆盖提示：若目标字段已有值（非 NULL），前端二次确认时提示可能覆盖。
            item_by_id = {it["id"]: it for it in episode_id_items}
            non_null_ids = set(non_null_values.keys())
            non_null_episode_count = len(
                {item_by_id[i]["episode_name"] for i in non_null_ids if i in item_by_id}
            )
            non_null_examples = []
            for i in list(non_null_ids)[:10]:
                it = item_by_id.get(i)
                if not it:
                    continue
                non_null_examples.append(
                    {
                        "episode_name": it.get("episode_name"),
                        "generated_from": it.get("generated_from"),
                        "data_format": it.get("data_format"),
                        "id": i,
                        "value": non_null_values.get(i),
                    }
                )

            missing_by_source: Dict[str, int] = {
                f"{g}/{f}": 0 for g, f in _target_sources
            }
            for m in missing:
                key = f"{m.get('generated_from')}/{m.get('data_format')}"
                missing_by_source[key] = missing_by_source.get(key, 0) + 1

            examples = ", ".join(
                f"{m['episode_name']}[{m['generated_from']}/{m['data_format']}]({m['id']})"
                for m in missing[:10]
            )
            hint = "可检查 device_id/collect_date/task_name 是否与数仓一致，必要时在请求里显式传入覆盖。"
            missing_breakdown = ", ".join(
                f"{k}={missing_by_source.get(k, 0)}" for k in missing_by_source.keys()
            )
            message = (
                f"数据库中未找到对应 dwd_episode 记录: missing_count={len(missing)} ({missing_breakdown}). "
                f"examples={examples}. {hint}"
                if missing
                else ""
            )

            exists_check = {
                "checked": True,
                "checked_count": len(episode_id_items),
                "missing_count": len(missing),
                "missing_examples": missing[:10],
                "message": message,
                "column": qc_col,
                "non_null_count": len(non_null_values),
                "non_null_episode_count": non_null_episode_count,
                "non_null_examples": non_null_examples,
            }

        stmts = []
        for generated_from, data_format in _target_sources:
            stmts.extend(
                PostgreSqlManager.build_qc_sync_statements(
                    base_dir=request.base_dir,
                    passed_episodes=list(request.passed or []),
                    failed_episodes=list(request.failed or []),
                    qc_type=request.mode,  # "validity" | "manual"
                    device_id=request.device_id,
                    collect_date=request.collect_date,
                    task_name=request.task_name,
                    generated_from=generated_from,
                    data_format=data_format,
                    prefer_compute_id=True,
                )
            )

        if request.check_exists and existing_ids is not None:
            # 跳过缺失记录：仅保留数据库中存在的目标 id。
            filtered = []
            for s in stmts:
                params = s.params
                if (
                    isinstance(params, tuple)
                    and len(params) >= 2
                    and params[1] in existing_ids
                ):
                    filtered.append(s)
            stmts = filtered
    except ValueError as e:
        # 输入/路径解析类错误：给前端可读原因（400），避免默认 generic 500。
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步到数据库失败: {str(e)}")

    if request.dry_run:
        _uvicorn_logger.info(
            "[sync-qc-to-db][dry-run] mode=%s base_dir=%s statement_count=%d",
            request.mode,
            request.base_dir,
            len(stmts),
        )
        for i, s in enumerate(stmts[:5], start=1):
            _uvicorn_logger.info(
                "[sync-qc-to-db][dry-run] #%d %s query=%s params=%s",
                i,
                s.description or "",
                s.query,
                s.params,
            )
        return {
            "success": True,
            "dry_run": True,
            "mode": request.mode,
            "statement_count": len(stmts),
            "episode_count": episode_count,
            "episode_update_count": episode_update_count,
            "statements": [
                {"query": s.query, "params": s.params, "description": s.description}
                for s in stmts
            ],
            "exists_check": exists_check,
        }

    try:
        db = PostgreSqlManager()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")

    try:
        updated_count = 0
        for s in stmts:
            updated_count += int(db.execute(s.query, s.params) or 0)
        return {
            "success": True,
            "dry_run": False,
            "mode": request.mode,
            "statement_count": len(stmts),
            "updated_count": updated_count,
            "episode_count": episode_count,
            "episode_update_count": episode_update_count,
            "exists_check": exists_check,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")
    finally:
        try:
            db.close()
        except Exception:
            pass
