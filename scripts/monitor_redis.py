#!/usr/bin/env python3
"""Redis 监控脚本 - 查看队列状态和统计信息"""

import redis
import argparse
import yaml
import sys
import json
from pathlib import Path
from datetime import datetime


def load_redis_config(config_path: str = 'config/redis_config.yaml') -> dict:
    """加载 Redis 配置"""
    config_file = Path(config_path)
    if not config_file.exists():
        project_root = Path(__file__).parent.parent
        config_file = project_root / config_path

    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def monitor_redis(config_path: str = 'config/redis_config.yaml', verbose: bool = False):
    """
    监控 Redis 队列和统计信息

    Args:
        config_path: Redis 配置文件路径
        verbose: 是否显示详细信息
    """
    # 加载配置
    config = load_redis_config(config_path)

    # 连接 Redis
    try:
        r = redis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            db=config['redis']['db'],
            password=config['redis'].get('password'),
            decode_responses=True
        )

        r.ping()

    except redis.ConnectionError as e:
        print(f"❌ Redis connection error: {e}", file=sys.stderr)
        print(f"Host: {config['redis']['host']}:{config['redis']['port']}", file=sys.stderr)
        sys.exit(1)

    queue_name = config['redis']['queue_name']
    sources = config.get('sources', [])

    print("\n" + "=" * 60)
    print("📊 LeRobot Redis Monitor")
    print("=" * 60)

    # 1. 队列状态
    print(f"\n📦 Queue Status")
    print(f"  Name: {queue_name}")

    pending_count = r.llen(queue_name)
    failed_count = r.llen(f"{queue_name}:failed")

    print(f"  Pending tasks: {pending_count}")
    print(f"  Failed tasks:  {failed_count}")

    # 显示待处理任务（如果有）
    if verbose and pending_count > 0:
        print(f"\n  Pending tasks preview (first 5):")
        tasks = r.lrange(queue_name, 0, 4)
        for i, task_json in enumerate(tasks, 1):
            task = json.loads(task_json)
            print(f"    {i}. {task['source']}/{task['episode_id']} (strategy: {task.get('strategy', 'N/A')})")

    # 2. 各数据源统计
    print(f"\n🤖 Sources Statistics")

    if not sources:
        # 自动发现数据源
        keys = r.keys("lerobot:stats:*:completed")
        sources = list(set([key.split(':')[2] for key in keys]))

    if sources:
        for source in sorted(sources):
            completed = int(r.get(f"lerobot:stats:{source}:completed") or 0)
            failed = int(r.get(f"lerobot:stats:{source}:failed") or 0)
            last_update = r.get(f"lerobot:stats:{source}:last_update")

            print(f"\n  {source}:")
            print(f"    Completed: {completed}")
            print(f"    Failed:    {failed}")

            if last_update:
                last_time = datetime.fromtimestamp(int(last_update))
                print(f"    Last update: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("  No data yet")

    # 3. 失败任务详情
    if failed_count > 0:
        print(f"\n❌ Failed Tasks")

        # 查找失败的 episode 信息
        failed_episodes = r.keys("lerobot:episode:*:*")
        failed_list = []

        for key in failed_episodes:
            data = r.hgetall(key)
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
    processed_keys = r.keys("lerobot:processed:*")
    print(f"\n✓ Total processed records: {len(processed_keys)}")

    # 5. Redis 信息
    if verbose:
        print(f"\n🔧 Redis Info")
        info = r.info('memory')
        print(f"  Used memory: {info['used_memory_human']}")
        print(f"  Keys: {r.dbsize()}")

    print("\n" + "=" * 60 + "\n")


def clear_failed_queue(config_path: str = 'config/redis_config.yaml'):
    """清空失败队列"""
    config = load_redis_config(config_path)
    r = redis.Redis(
        host=config['redis']['host'],
        port=config['redis']['port'],
        db=config['redis']['db'],
        password=config['redis'].get('password'),
        decode_responses=True
    )

    queue_name = config['redis']['queue_name']
    failed_queue = f"{queue_name}:failed"

    count = r.llen(failed_queue)
    if count > 0:
        r.delete(failed_queue)
        print(f"✓ Cleared {count} failed tasks")
    else:
        print("No failed tasks to clear")


def retry_failed(config_path: str = 'config/redis_config.yaml'):
    """重试失败的任务"""
    config = load_redis_config(config_path)
    r = redis.Redis(
        host=config['redis']['host'],
        port=config['redis']['port'],
        db=config['redis']['db'],
        password=config['redis'].get('password'),
        decode_responses=True
    )

    queue_name = config['redis']['queue_name']
    failed_queue = f"{queue_name}:failed"

    count = 0
    while True:
        task_json = r.rpop(failed_queue)
        if not task_json:
            break

        # 重新推入主队列
        r.lpush(queue_name, task_json)
        count += 1

    if count > 0:
        print(f"✓ Moved {count} failed tasks back to queue")
    else:
        print("No failed tasks to retry")


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

    if args.clear_failed:
        clear_failed_queue(args.config)
    elif args.retry_failed:
        retry_failed(args.config)
    else:
        monitor_redis(args.config, args.verbose)


if __name__ == '__main__':
    main()
