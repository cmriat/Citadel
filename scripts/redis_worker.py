#!/usr/bin/env python3
"""Redis Worker 服务 - 监听队列并处理转换任务"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import redis

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.redis.client import RedisClient
from lerobot_converter.redis.task_queue import TaskQueue
from lerobot_converter.redis.worker import RedisWorker


def main():
    """Redis Worker 主入口"""
    parser = argparse.ArgumentParser(
        description='Redis Worker - 处理 LeRobot 数据转换任务'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/redis_config.yaml',
        help='Redis 配置文件路径'
    )

    args = parser.parse_args()

    try:
        # 1. 初始化 Redis 客户端
        redis_client = RedisClient(args.config)

        if not redis_client.ping():
            print(f"\n❌ Cannot connect to Redis", file=sys.stderr)
            print(f"  Host: {redis_client.config['redis']['host']}:{redis_client.config['redis']['port']}", file=sys.stderr)
            sys.exit(1)

        print(f"✓ Connected to Redis: {redis_client.config['redis']['host']}:{redis_client.config['redis']['port']}")

        # 2. 初始化任务队列
        task_queue = TaskQueue(
            redis_client.client,
            redis_client.get_queue_name()
        )

        print(f"✓ Queue: {task_queue.queue_name}")

        # 3. 初始化 Worker
        worker_config = redis_client.get_worker_config()
        conversion_config = redis_client.get_conversion_config()

        worker = RedisWorker(
            output_pattern=redis_client.get_output_pattern(),
            config_template=conversion_config['config_template'],
            default_strategy=conversion_config['strategy']
        )

        max_workers = worker_config.get('max_workers', 2)
        poll_interval = worker_config.get('poll_interval', 1)

        print(f"✓ Max workers: {max_workers}")

        # 4. 启动 Worker 主循环
        print(f"\n🚀 Worker started, waiting for tasks...")
        print(f"Press Ctrl+C to stop\n")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            try:
                while True:
                    # 阻塞等待任务
                    task_data = task_queue.get(timeout=poll_interval)

                    if task_data:
                        # 提交到线程池处理
                        executor.submit(worker.process_task, task_data, task_queue)

            except KeyboardInterrupt:
                print("\n\n⚠️  Shutting down...")
                print("✓ Worker stopped\n")

    except redis.ConnectionError as e:
        print(f"\n❌ Redis connection error: {e}", file=sys.stderr)
        print("请确保 Redis 服务器正在运行。\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
