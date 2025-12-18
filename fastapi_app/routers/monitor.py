"""监控 API"""

import logging
import asyncio
from typing import List
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..schemas.models import QueueStats, EpisodeInfo, EpisodeListResponse
from ..services.scanner_service import scanner_service
from ..services.worker_service import worker_service
from .config import get_current_config

logger = logging.getLogger(__name__)
router = APIRouter()

# WebSocket 连接管理
_websocket_connections: List[WebSocket] = []


async def broadcast_log(message: str):
    """广播日志消息到所有 WebSocket 连接"""
    disconnected = []
    for ws in _websocket_connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)

    # 清理断开的连接
    for ws in disconnected:
        if ws in _websocket_connections:
            _websocket_connections.remove(ws)


def sync_log_callback(message: str):
    """同步日志回调（用于服务层）"""
    # 创建一个新的事件循环任务来发送消息
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast_log(message))
        else:
            loop.run_until_complete(broadcast_log(message))
    except RuntimeError:
        # 如果没有事件循环，忽略
        pass


@router.get("/stats", response_model=QueueStats)
async def get_queue_stats():
    """获取队列统计"""
    config = get_current_config()

    try:
        import redis

        redis_config = config.redis
        r = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            password=redis_config.password,
            decode_responses=True
        )

        # 获取队列长度
        queue_name = "lerobot:episodes"
        pending = r.llen(queue_name)
        failed = r.llen(f"{queue_name}:failed")

        # 获取处理中的数量（pending set）
        processing = r.scard(f"{queue_name}:pending")

        # 统计完成数量
        completed = 0
        for key in r.scan_iter("lerobot:processed:*"):
            completed += 1

        return QueueStats(
            pending=pending,
            processing=processing,
            completed=completed,
            failed=failed
        )

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return QueueStats()


@router.get("/episodes", response_model=EpisodeListResponse)
async def get_episodes(limit: int = 20, offset: int = 0):
    """获取最近处理的 Episode 列表"""
    config = get_current_config()

    try:
        import redis

        redis_config = config.redis
        r = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            password=redis_config.password,
            decode_responses=True
        )

        episodes: List[EpisodeInfo] = []

        # 获取已完成的 episodes
        completed_keys = list(r.scan_iter("lerobot:episode:*", count=100))
        total = len(completed_keys)

        # 分页
        paginated_keys = completed_keys[offset:offset + limit]

        for key in paginated_keys:
            try:
                data = r.hgetall(key)
                if data:
                    episodes.append(EpisodeInfo(
                        episode_id=data.get("episode_id", key.split(":")[-1]),
                        status=data.get("status", "unknown"),
                        timestamp=data.get("timestamp", ""),
                        strategy=data.get("strategy"),
                        frames=int(data.get("frames", 0)) if data.get("frames") else None,
                        error=data.get("error")
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse episode data for {key}: {e}")

        # 按时间排序（最新的在前）
        episodes.sort(key=lambda x: x.timestamp, reverse=True)

        return EpisodeListResponse(episodes=episodes, total=total)

    except Exception as e:
        logger.error(f"Failed to get episodes: {e}")
        return EpisodeListResponse(episodes=[], total=0)


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket 日志推送"""
    await websocket.accept()
    _websocket_connections.append(websocket)

    # 注册日志回调
    scanner_service.add_log_callback(sync_log_callback)
    worker_service.add_log_callback(sync_log_callback)

    try:
        # 发送欢迎消息
        timestamp = datetime.now().strftime("%H:%M:%S")
        await websocket.send_text(f"{timestamp} [System] WebSocket connected")

        # 保持连接
        while True:
            try:
                # 等待客户端消息（心跳）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 发送心跳
                await websocket.send_text("heartbeat")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")

    finally:
        # 移除回调和连接
        scanner_service.remove_log_callback(sync_log_callback)
        worker_service.remove_log_callback(sync_log_callback)
        if websocket in _websocket_connections:
            _websocket_connections.remove(websocket)
