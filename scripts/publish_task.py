#!/usr/bin/env python3
"""任务发布工具 - 将 Episode 发布到 Redis 队列"""

import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.core.task import ConversionTask, AlignmentStrategy
from lerobot_converter.redis.client import RedisClient
from lerobot_converter.redis.task_queue import TaskQueue


def publish_episode(
    episode_id: str,
    source: str = None,
    strategy: str = None,
    config_path: str = 'config/redis_config.yaml'
) -> bool:
    """发布 Episode 转换任务到 Redis 队列

    Args:
        episode_id: Episode ID (如 episode_0007)
        source: 数据源ID (如 robot_1)，默认从环境变量 ROBOT_ID 读取
        strategy: 对齐策略，默认从配置文件读取
        config_path: Redis 配置文件路径

    Returns:
        bool: 是否成功发布
    """
    try:
        # 1. 初始化 Redis 客户端
        redis_client = RedisClient(config_path)

        if not redis_client.ping():
            print(f"✗ Redis connection failed", file=sys.stderr)
            return False

        # 2. 获取数据源
        if source is None:
            source = os.environ.get('ROBOT_ID', 'robot_1')

        # 3. 获取策略
        if strategy is None:
            strategy = redis_client.get_conversion_config()['strategy']

        # 4. 创建任务
        task = ConversionTask(
            episode_id=episode_id,
            source=source,
            strategy=AlignmentStrategy(strategy)
        )

        # 5. 发布到队列
        task_queue = TaskQueue(
            redis_client.client,
            redis_client.get_queue_name()
        )

        if task_queue.publish(task):
            print(f"✓ Published: {source}/{episode_id} (strategy: {strategy})")
            print(f"  Queue: {task_queue.queue_name}")
            print(f"  Length: {task_queue.get_pending_count()}")
            return True
        else:
            print(f"✗ Failed to publish task", file=sys.stderr)
            return False

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='发布 LeRobot Episode 转换任务到 Redis 队列',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用默认配置
  python scripts/publish_task.py --episode episode_0007

  # 指定数据源
  python scripts/publish_task.py --episode episode_0007 --source robot_1

  # 使用环境变量指定数据源
  export ROBOT_ID=robot_2
  python scripts/publish_task.py --episode episode_0008

  # 指定策略
  python scripts/publish_task.py --episode episode_0007 --strategy nearest

采集程序中使用:
  from scripts.publish_task import publish_episode
  publish_episode('episode_0007', source='robot_1')
        """
    )

    parser.add_argument(
        '--episode',
        type=str,
        required=True,
        help='Episode ID (如: episode_0007)'
    )

    parser.add_argument(
        '--source',
        type=str,
        help='数据源ID (如: robot_1)，默认从环境变量 ROBOT_ID 读取'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        choices=['nearest', 'chunking', 'window'],
        help='对齐策略，默认从配置文件读取'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/redis_config.yaml',
        help='Redis 配置文件路径'
    )

    args = parser.parse_args()

    success = publish_episode(
        episode_id=args.episode,
        source=args.source,
        strategy=args.strategy,
        config_path=args.config
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
