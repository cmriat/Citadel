"""Redis 任务队列管理"""

import json
import time
from typing import Optional
import redis

from ..core.task import ConversionTask


class TaskQueue:
    """Redis 任务队列管理器

    职责：
    - 任务的发布和获取
    - 去重检查
    - 统计信息记录
    - 失败任务管理
    """

    def __init__(self, redis_client: redis.Redis, queue_name: str):
        """初始化任务队列

        Args:
            redis_client: Redis 客户端实例
            queue_name: 队列名称
        """
        self.redis = redis_client
        self.queue_name = queue_name
        self.failed_queue = f"{queue_name}:failed"
        self.processed_prefix = "lerobot:processed"
        self.stats_prefix = "lerobot:stats"
        self.episode_prefix = "lerobot:episode"

    def publish(self, task: ConversionTask) -> bool:
        """发布任务到队列

        Args:
            task: ConversionTask 对象

        Returns:
            是否成功发布
        """
        try:
            self.redis.lpush(
                self.queue_name,
                json.dumps(task.to_dict())
            )
            return True
        except redis.RedisError:
            return False

    def get(self, timeout: int = 1) -> Optional[dict]:
        """阻塞获取任务

        Args:
            timeout: 阻塞超时时间（秒）

        Returns:
            任务字典或 None
        """
        result = self.redis.brpop(self.queue_name, timeout=timeout)
        if result:
            _, task_json = result
            return json.loads(task_json)
        return None

    def is_processed(self, source: str, episode_id: str) -> bool:
        """检查任务是否已处理

        Args:
            source: 数据源ID
            episode_id: Episode ID

        Returns:
            True if 已处理
        """
        key = f"{self.processed_prefix}:{source}:{episode_id}"
        return self.redis.exists(key) > 0

    def mark_processed(self, source: str, episode_id: str, ttl_days: int = 30):
        """标记任务已处理

        Args:
            source: 数据源ID
            episode_id: Episode ID
            ttl_days: 保留天数（TTL）
        """
        key = f"{self.processed_prefix}:{source}:{episode_id}"
        self.redis.setex(key, ttl_days * 86400, "1")

    def record_stats(self, source: str, status: str):
        """记录统计信息

        Args:
            source: 数据源ID
            status: 状态 (completed/failed)
        """
        # 增加计数
        self.redis.incr(f"{self.stats_prefix}:{source}:{status}")

        # 记录最后更新时间
        self.redis.set(
            f"{self.stats_prefix}:{source}:last_update",
            int(time.time())
        )

    def save_episode_info(self, source: str, episode_id: str, status: str, error: str = None):
        """保存 episode 处理信息

        Args:
            source: 数据源ID
            episode_id: Episode ID
            status: 状态
            error: 错误信息（如果有）
        """
        key = f"{self.episode_prefix}:{source}:{episode_id}"
        data = {
            'status': status,
            'timestamp': int(time.time())
        }
        if error:
            data['error'] = error

        self.redis.hset(key, mapping=data)
        # 设置过期时间（7天后删除）
        self.redis.expire(key, 86400 * 7)

    def move_to_failed(self, task_data: dict):
        """移动到失败队列

        Args:
            task_data: 任务字典
        """
        self.redis.lpush(self.failed_queue, json.dumps(task_data))

    def get_pending_count(self) -> int:
        """获取待处理任务数"""
        return self.redis.llen(self.queue_name)

    def get_failed_count(self) -> int:
        """获取失败任务数"""
        return self.redis.llen(self.failed_queue)

    def get_stats(self, source: str) -> dict:
        """获取数据源的统计信息

        Args:
            source: 数据源ID

        Returns:
            统计字典
        """
        return {
            'completed': int(self.redis.get(f"{self.stats_prefix}:{source}:completed") or 0),
            'failed': int(self.redis.get(f"{self.stats_prefix}:{source}:failed") or 0),
            'last_update': self.redis.get(f"{self.stats_prefix}:{source}:last_update")
        }
