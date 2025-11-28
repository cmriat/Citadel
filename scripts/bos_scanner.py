#!/usr/bin/env python3
"""BOS 扫描器 - 定时扫描 BOS 上的新 episode 并发布到 Redis Stream"""

import argparse
import sys
import os
import time
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.bos import BosClient, EpisodeScanner
from lerobot_converter.core.task import ConversionTask, AlignmentStrategy
from lerobot_converter.redis.client import RedisClient
from lerobot_converter.redis.task_queue import TaskQueue


def setup_logging(level: str = 'INFO'):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    parser = argparse.ArgumentParser(description='BOS Episode Scanner')
    parser.add_argument(
        '--config',
        default='config/bos_config.yaml',
        help='BOS 配置文件路径'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='只扫描一次然后退出（不循环）'
    )
    parser.add_argument(
        '--interval',
        type=int,
        help='扫描间隔（秒），覆盖配置文件中的值'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别'
    )
    parser.add_argument(
        '--full-scan',
        action='store_true',
        help='强制完整扫描（忽略增量扫描位置）'
    )

    args = parser.parse_args()

    # 设置日志
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # 1. 初始化 BOS 客户端
        logger.info("Initializing BOS client...")
        bos_client = BosClient(config_path=args.config)

        # 测试连接
        if not bos_client.test_connection():
            logger.error("Failed to connect to BOS. Please check your configuration.")
            sys.exit(1)

        # 2. 初始化 Redis 客户端（使用 RedisClient）
        logger.info("Initializing Redis client...")
        redis_client = RedisClient(args.config)

        if not redis_client.ping():
            logger.error(f"✗ Cannot connect to Redis")
            logger.error(f"  Host: {redis_client.config['redis']['host']}:{redis_client.config['redis']['port']}")
            sys.exit(1)

        logger.info("✓ Redis connection successful")

        # 3. 初始化任务队列
        task_queue = TaskQueue(
            redis_client.client,
            redis_client.get_queue_name()
        )
        logger.info(f"✓ Queue: {task_queue.queue_name}")

        # 4. 初始化扫描器（使用 TaskQueue 实例来统一去重逻辑）
        scanner = EpisodeScanner(bos_client, task_queue)

        # 4. 如果使用 --full-scan，清除增量扫描位置
        scanner_config = bos_client.get_scanner_config()
        if args.full_scan:
            incremental_key = scanner_config.get('incremental_key', 'bos:last_scanned_key')
            deleted_count = redis_client.client.delete(incremental_key)
            if deleted_count > 0:
                logger.info(f"✓ Cleared incremental scan position (full scan mode)")
            else:
                logger.info(f"✓ Full scan mode enabled (no previous scan position found)")

        # 5. 获取扫描间隔
        scan_interval = args.interval if args.interval else scanner_config.get('interval', 120)

        logger.info(f"Starting BOS scanner (interval: {scan_interval}s)")
        logger.info(f"Watching prefix: {bos_client.get_raw_data_prefix()}")

        # 5. 扫描循环
        scan_count = 0
        while True:
            scan_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Scan #{scan_count} started")
            logger.info(f"{'='*60}")

            try:
                # 扫描并过滤出需要处理的 episode
                ready_episodes = scanner.scan_and_filter()

                # 发布到 Redis Stream
                if ready_episodes:
                    for ep_data in ready_episodes:
                        episode_id = ep_data['episode_id']

                        # 创建转换任务
                        task = ConversionTask(
                            episode_id=episode_id,
                            source='bos',  # 标记为 BOS 数据源
                            strategy=AlignmentStrategy.CHUNKING,
                            config_overrides={
                                'bos_metadata': ep_data['metadata']
                            }
                        )

                        # 发布到 Redis 队列（使用 TaskQueue）
                        if task_queue.publish(task):
                            logger.info(f"✅ Published task for {episode_id} to Redis Queue")
                        else:
                            logger.error(f"❌ Failed to publish task for {episode_id}")

                    logger.info(f"\n📊 Summary: Published {len(ready_episodes)} episodes")
                else:
                    logger.info("No new episodes found")

            except Exception as e:
                logger.error(f"Error during scan: {e}", exc_info=True)

            # 如果是 --once 模式，退出
            if args.once:
                logger.info("One-time scan completed, exiting...")
                break

            # 等待下一次扫描
            logger.info(f"\n💤 Sleeping for {scan_interval} seconds...")
            logger.info(f"Next scan at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + scan_interval))}")
            time.sleep(scan_interval)

    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Scanner stopped by user")
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
