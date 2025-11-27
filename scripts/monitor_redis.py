#!/usr/bin/env python3
"""Redis 监控脚本 - 查看队列状态和统计信息"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.redis.client import RedisClient
from lerobot_converter.redis.task_queue import TaskQueue
from lerobot_converter.redis.monitoring import RedisMonitor


def main():
    parser = argparse.ArgumentParser(
        description='监控 LeRobot Redis 队列和统计信息'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/redis_config.yaml',
        help='Redis 配置文件路径'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细信息'
    )

    parser.add_argument(
        '--clear-failed',
        action='store_true',
        help='清空失败队列'
    )

    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='重试失败的任务'
    )

    args = parser.parse_args()

    try:
        # 1. 初始化 Redis 客户端
        redis_client = RedisClient(args.config)

        if not redis_client.ping():
            print(f"❌ Redis connection error", file=sys.stderr)
            print(f"Host: {redis_client.config['redis']['host']}:{redis_client.config['redis']['port']}", file=sys.stderr)
            sys.exit(1)

        # 2. 初始化任务队列和监控器
        task_queue = TaskQueue(
            redis_client.client,
            redis_client.get_queue_name()
        )

        monitor = RedisMonitor(
            redis_client.client,
            task_queue,
            redis_client.get_sources()
        )

        # 3. 执行操作
        if args.clear_failed:
            monitor.clear_failed_queue()
        elif args.retry_failed:
            monitor.retry_failed()
        else:
            monitor.show_status(verbose=args.verbose)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
