"""Redis 任务队列管理"""

import json
import time
import logging
from typing import Optional
import redis

from ..core.task import ConversionTask

logger = logging.getLogger(__name__)


class TaskQueue:
    """Redis 任务队列管理器

    职责：
    - 任务的发布和获取
    - 去重检查
    - 统计信息记录
    - 失败任务管理
    """

    # Lua 脚本：原子性检查并发布任务
    _PUBLISH_SCRIPT = """
    if redis.call('sismember', KEYS[1], ARGV[1]) == 1 then
        return 0
    end
    redis.call('sadd', KEYS[1], ARGV[1])
    redis.call('lpush', KEYS[2], ARGV[2])
    return 1
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
        self.pending_set = f"{queue_name}:pending"  # 已发布但未完成的任务集合
        self.processed_prefix = "lerobot:processed"
        self.stats_prefix = "lerobot:stats"
        self.episode_prefix = "lerobot:episode"

        # 注册 Lua 脚本
        self._publish_sha = self.redis.script_load(self._PUBLISH_SCRIPT)

    def publish(self, task: ConversionTask) -> bool:
        """发布任务到队列（原子操作）

        使用 Lua 脚本确保检查和发布的原子性，避免重复发布。

        Args:
            task: ConversionTask 对象

        Returns:
            是否成功发布（False 表示任务已存在或发布失败）
        """
        try:
            task_key = f"{task.source}:{task.episode_id}"
            task_json = json.dumps(task.to_dict())

            # 使用 Lua 脚本原子性检查并发布
            result = self.redis.evalsha(
                self._publish_sha,
                2,  # 2 个 KEYS
                self.pending_set,  # KEYS[1]
                self.queue_name,   # KEYS[2]
                task_key,          # ARGV[1]
                task_json          # ARGV[2]
            )

            if result == 0:
                logger.debug(f"Task {task_key} already in pending set, skipping")
                return False
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to publish task {task.episode_id} to queue: {e}")
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
            try:
                return json.loads(task_json)
            except json.JSONDecodeError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Invalid JSON in task queue: {task_json[:200]}... Error: {e}")
                # 将损坏的任务移到失败队列
                self.redis.lpush(self.failed_queue, task_json)
                return None
        return None

    def is_processed(self, source: str, episode_id: str, namespace: str = None) -> bool:
        """检查任务是否已处理

        Args:
            source: 数据源ID
            episode_id: Episode ID
            namespace: 可选的命名空间（用于隔离不同配置目录的记录）

        Returns:
            True if 已处理
        """
        if namespace:
            key = f"{self.processed_prefix}:{source}:{namespace}:{episode_id}"
        else:
            key = f"{self.processed_prefix}:{source}:{episode_id}"
        return self.redis.exists(key) > 0

    def mark_processed(self, source: str, episode_id: str, ttl_days: int = 30, namespace: str = None):
        """标记任务已处理（原子操作）

        Args:
            source: 数据源ID
            episode_id: Episode ID
            ttl_days: 保留天数（TTL）
            namespace: 可选的命名空间（用于隔离不同配置目录的记录）
        """
        if namespace:
            key = f"{self.processed_prefix}:{source}:{namespace}:{episode_id}"
        else:
            key = f"{self.processed_prefix}:{source}:{episode_id}"

        task_key = f"{source}:{episode_id}"

        # 使用 pipeline 确保原子性
        pipe = self.redis.pipeline()
        pipe.setex(key, ttl_days * 86400, "1")
        pipe.srem(self.pending_set, task_key)
        pipe.execute()

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

    def move_to_failed(self, task_data: dict, ttl_days: int = 7):
        """移动到失败队列

        Args:
            task_data: 任务字典
            ttl_days: 失败队列保留天数（默认7天）
        """
        source = task_data.get('source', '')
        episode_id = task_data.get('episode_id', '')
        task_key = f"{source}:{episode_id}" if source and episode_id else None

        # 使用 pipeline 确保原子性
        pipe = self.redis.pipeline()
        pipe.lpush(self.failed_queue, json.dumps(task_data))
        pipe.expire(self.failed_queue, ttl_days * 86400)  # 设置 TTL 防止无限积累
        if task_key:
            pipe.srem(self.pending_set, task_key)
        pipe.execute()

    def requeue(self, task_data: dict):
        """将任务放回队列（用于中断恢复）

        使用 rpush 放到队列右端，由于 brpop 从右端取出，
        所以该任务会被优先处理。

        注意：不从 pending 集合中移除，因为任务仍在等待处理

        Args:
            task_data: 任务字典
        """
        self.redis.rpush(self.queue_name, json.dumps(task_data))

    def get_pending_count(self) -> int:
        """获取待处理任务数（队列中）"""
        return self.redis.llen(self.queue_name)

    def get_pending_set_count(self) -> int:
        """获取已发布但未完成的任务数"""
        return self.redis.scard(self.pending_set)

    def is_pending(self, source: str, episode_id: str) -> bool:
        """检查任务是否在 pending 集合中（已发布但未完成）

        Args:
            source: 数据源ID
            episode_id: Episode ID

        Returns:
            bool: 是否在 pending 集合中
        """
        task_key = f"{source}:{episode_id}"
        return self.redis.sismember(self.pending_set, task_key)

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
