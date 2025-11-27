"""Redis 监控功能"""

import json
from datetime import datetime
from typing import List, Dict
import redis

from .task_queue import TaskQueue


class RedisMonitor:
    """Redis 监控器

    职责：
    - 查看队列状态
    - 显示统计信息
    - 管理失败任务
    """

    def __init__(self, redis_client: redis.Redis, task_queue: TaskQueue, sources: List[str]):
        """初始化监控器

        Args:
            redis_client: Redis 客户端实例
            task_queue: TaskQueue 实例
            sources: 数据源列表
        """
        self.redis = redis_client
        self.task_queue = task_queue
        self.sources = sources

    def show_status(self, verbose: bool = False):
        """显示队列状态和统计信息

        Args:
            verbose: 是否显示详细信息
        """
        print("\n" + "=" * 60)
        print("📊 LeRobot Redis Monitor")
        print("=" * 60)

        # 1. 队列状态
        print(f"\n📦 Queue Status")
        print(f"  Name: {self.task_queue.queue_name}")

        pending_count = self.task_queue.get_pending_count()
        failed_count = self.task_queue.get_failed_count()

        print(f"  Pending tasks: {pending_count}")
        print(f"  Failed tasks:  {failed_count}")

        # 显示待处理任务
        if verbose and pending_count > 0:
            print(f"\n  Pending tasks preview (first 5):")
            tasks = self.redis.lrange(self.task_queue.queue_name, 0, 4)
            for i, task_json in enumerate(tasks, 1):
                task = json.loads(task_json)
                print(f"    {i}. {task['source']}/{task['episode_id']} (strategy: {task.get('strategy', 'N/A')})")

        # 2. 各数据源统计
        print(f"\n🤖 Sources Statistics")

        if not self.sources:
            # 自动发现数据源
            keys = self.redis.keys(f"{self.task_queue.stats_prefix}:*:completed")
            self.sources = list(set([key.split(':')[2] for key in keys]))

        if self.sources:
            for source in sorted(self.sources):
                stats = self.task_queue.get_stats(source)
                print(f"\n  {source}:")
                print(f"    Completed: {stats['completed']}")
                print(f"    Failed:    {stats['failed']}")

                if stats['last_update']:
                    last_time = datetime.fromtimestamp(int(stats['last_update']))
                    print(f"    Last update: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("  No data yet")

        # 3. 失败任务详情
        if failed_count > 0:
            print(f"\n❌ Failed Tasks")

            # 查找失败的 episode 信息
            failed_episodes = self.redis.keys(f"{self.task_queue.episode_prefix}:*:*")
            failed_list = []

            for key in failed_episodes:
                data = self.redis.hgetall(key)
                if data.get('status') == 'failed':
                    parts = key.split(':')
                    source = parts[2]
                    episode_id = parts[3]
                    error = data.get('error', 'Unknown error')
                    timestamp = int(data.get('timestamp', 0))

                    failed_list.append({
                        'source': source,
                        'episode_id': episode_id,
                        'error': error,
                        'time': datetime.fromtimestamp(timestamp)
                    })

            # 按时间排序
            failed_list.sort(key=lambda x: x['time'], reverse=True)

            # 显示最近的失败任务
            display_count = min(10, len(failed_list))
            if display_count > 0:
                print(f"  Recent {display_count} failures:")
                for i, item in enumerate(failed_list[:display_count], 1):
                    print(f"    {i}. {item['source']}/{item['episode_id']}")
                    print(f"       Time: {item['time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    if verbose:
                        print(f"       Error: {item['error']}")

        # 4. 已处理记录数量
        processed_keys = self.redis.keys(f"{self.task_queue.processed_prefix}:*")
        print(f"\n✓ Total processed records: {len(processed_keys)}")

        # 5. Redis 信息
        if verbose:
            print(f"\n🔧 Redis Info")
            info = self.redis.info('memory')
            print(f"  Used memory: {info['used_memory_human']}")
            print(f"  Keys: {self.redis.dbsize()}")

        print("\n" + "=" * 60 + "\n")

    def clear_failed_queue(self):
        """清空失败队列"""
        count = self.task_queue.get_failed_count()
        if count > 0:
            self.redis.delete(self.task_queue.failed_queue)
            print(f"✓ Cleared {count} failed tasks")
        else:
            print("No failed tasks to clear")

    def retry_failed(self):
        """重试失败的任务"""
        count = 0
        while True:
            task_json = self.redis.rpop(self.task_queue.failed_queue)
            if not task_json:
                break

            # 重新推入主队列
            self.redis.lpush(self.task_queue.queue_name, task_json)
            count += 1

        if count > 0:
            print(f"✓ Moved {count} failed tasks back to queue")
        else:
            print("No failed tasks to retry")
