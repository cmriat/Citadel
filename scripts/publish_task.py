#!/usr/bin/env python3
"""任务发布工具 - 将 Episode 发布到 Redis 队列"""

import redis
import json
import argparse
import yaml
import sys
import os
from pathlib import Path
import time


def load_redis_config(config_path: str = 'config/redis_config.yaml') -> dict:
    """加载 Redis 配置"""
    config_file = Path(config_path)
    if not config_file.exists():
        # 尝试从项目根目录查找
        project_root = Path(__file__).parent.parent
        config_file = project_root / config_path

    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def publish_episode(
    episode_id: str,
    source: str = None,
    strategy: str = None,
    config_path: str = 'config/redis_config.yaml',
    redis_host: str = None,
    redis_port: int = None
):
    """
    发布 Episode 转换任务到 Redis 队列

    Args:
        episode_id: Episode ID (如 episode_0007)
        source: 数据源ID (如 robot_1)，默认从环境变量 ROBOT_ID 读取
        strategy: 对齐策略，默认从配置文件读取
        config_path: Redis 配置文件路径
        redis_host: Redis 主机（覆盖配置文件）
        redis_port: Redis 端口（覆盖配置文件）

    Returns:
        bool: 是否成功发布
    """
    # 加载配置
    config = load_redis_config(config_path)

    # 获取数据源
    if source is None:
        source = os.environ.get('ROBOT_ID', 'robot_1')

    # 获取策略
    if strategy is None:
        strategy = config['conversion']['strategy']

    # Redis 连接参数
    host = redis_host or config['redis']['host']
    port = redis_port or config['redis']['port']
    db = config['redis']['db']
    password = config['redis'].get('password')
    queue_name = config['redis']['queue_name']

    try:
        # 连接 Redis
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )

        # 测试连接
        r.ping()

        # 构造任务
        task = {
            'episode_id': episode_id,
            'source': source,
            'strategy': strategy,
            'timestamp': time.time()
        }

        # 发布到队列
        r.lpush(queue_name, json.dumps(task))

        print(f"✓ Published: {source}/{episode_id} (strategy: {strategy})")
        print(f"  Queue: {queue_name}")
        print(f"  Length: {r.llen(queue_name)}")

        return True

    except redis.ConnectionError as e:
        print(f"✗ Redis connection error: {e}", file=sys.stderr)
        print(f"  Host: {host}:{port}", file=sys.stderr)
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

  # 覆盖 Redis 地址
  python scripts/publish_task.py --episode episode_0007 --redis-host 192.168.1.100

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

    parser.add_argument(
        '--redis-host',
        type=str,
        help='Redis 主机地址（覆盖配置文件）'
    )

    parser.add_argument(
        '--redis-port',
        type=int,
        help='Redis 端口（覆盖配置文件）'
    )

    args = parser.parse_args()

    success = publish_episode(
        episode_id=args.episode,
        source=args.source,
        strategy=args.strategy,
        config_path=args.config,
        redis_host=args.redis_host,
        redis_port=args.redis_port
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
