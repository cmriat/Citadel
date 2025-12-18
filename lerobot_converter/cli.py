#!/usr/bin/env python3
"""LeRobot Converter 统一CLI入口

提供所有功能的统一命令行接口：
- convert: 本地数据转换
- worker: Redis Worker服务
- scanner: BOS扫描器
- publish: 发布转换任务
- monitor: 监控Redis队列
- test: 测试BOS完整流程
"""

import sys
import logging
from pathlib import Path
import click

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@click.group()
@click.version_option(version="2.1.0", prog_name="lerobot-convert")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose):
    """LeRobot v2.1 数据转换工具

    统一的命令行界面，支持本地转换、Redis多数据源流处理、BOS自动化等功能。
    """
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )


@cli.command()
@click.option('--config', '-c', required=True, type=click.Path(exists=True),
              help='策略配置文件路径 (e.g., config/strategies/chunking.yaml)')
@click.option('--episode-id', '-e', help='转换单个episode')
@click.option('--strategy', type=click.Choice(['nearest', 'chunking', 'window']),
              help='覆盖配置的对齐策略')
@click.option('--output', '-o', help='覆盖输出目录')
def convert(config, episode_id, strategy, output):
    """本地数据转换

    将原始机器人数据转换为LeRobot v2.1格式。

    示例：
      lerobot-convert convert -c config/strategies/chunking.yaml -e episode_0001
    """
    from lerobot_converter.pipeline.converter import LeRobotConverter
    from lerobot_converter.pipeline.config import load_config

    click.echo(f"📂 Loading config: {config}")
    converter_config = load_config(config)

    # 应用命令行参数覆盖
    if strategy:
        converter_config['alignment']['strategy'] = strategy
        click.echo(f"✓ Strategy override: {strategy}")

    if output:
        converter_config['output']['base_path'] = output
        click.echo(f"✓ Output override: {output}")

    click.echo("\n" + "="*60)
    click.echo("LeRobot v2.1 Converter")
    click.echo("="*60)
    click.echo(f"Strategy: {converter_config['alignment']['strategy']}")
    click.echo(f"Output: {converter_config['output']['base_path']}")
    click.echo("="*60 + "\n")

    # 创建转换器
    converter = LeRobotConverter(converter_config)

    # 执行转换
    if episode_id:
        click.echo(f"🎯 Converting single episode: {episode_id}")
        converter.convert(episode_id=episode_id)
    else:
        click.echo("🔄 Converting all episodes...")
        converter.convert()

    click.echo("\n✅ Conversion completed!")


@cli.command()
@click.option('--config', '-c', default='config/storage.yaml', type=click.Path(exists=True),
              help='存储配置文件 (default: config/storage.yaml)')
@click.option('--source', '-s', help='数据源ID (覆盖配置文件)')
@click.option('--max-workers', type=int, help='最大并发worker数')
def worker(config, source, max_workers):
    """启动Redis Worker服务

    从Redis队列消费转换任务并执行。支持多线程并发处理。

    示例：
      lerobot-convert worker -c config/storage.yaml -s robot_1 --max-workers 4
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    from lerobot_converter.redis import RedisClient, TaskQueue, RedisWorker

    click.echo(f"📂 Loading config: {config}")

    # 初始化 Redis 客户端（从配置文件）
    redis_client = RedisClient(config)

    if not redis_client.ping():
        click.echo("❌ Redis connection failed", err=True)
        sys.exit(1)

    click.echo("✓ Redis connection successful")

    # 获取配置（通过 RedisClient）
    worker_config = redis_client.get_worker_config()

    # 应用命令行参数覆盖
    if max_workers:
        worker_config['max_workers'] = max_workers

    num_workers = worker_config.get('max_workers', 2)
    poll_interval = worker_config.get('poll_interval', 1)

    # 数据源
    if source:
        sources = [source]
    else:
        sources = redis_client.get_sources()

    click.echo(f"✓ Data sources: {', '.join(sources)}")
    click.echo(f"✓ Max workers: {num_workers}")

    # 创建Worker
    worker_instance = RedisWorker(
        output_pattern=redis_client.get_output_pattern(),
        config_template=redis_client.get_conversion_config().get('config_template', 'config/strategies/chunking.yaml'),
        default_strategy=redis_client.get_conversion_config().get('strategy', 'chunking'),
        bos_config_path=config  # 传递完整配置以支持BOS源
    )

    task_queue = TaskQueue(redis_client.client, redis_client.get_queue_name())

    click.echo("\n🚀 Starting Redis Worker Pool...")
    click.echo(f"Queue: {task_queue.queue_name}")
    click.echo(f"Worker threads: {num_workers}")
    click.echo("Press Ctrl+C to stop\n")

    # 用于控制worker线程的停止标志
    stop_event = threading.Event()

    def worker_loop(worker_id: int):
        """单个worker线程的主循环"""
        logger = logging.getLogger(__name__)
        logger.info(f"Worker-{worker_id} started")

        while not stop_event.is_set():
            try:
                task_data = task_queue.get(timeout=poll_interval)
                if task_data:
                    logger.info(f"Worker-{worker_id} processing task...")
                    worker_instance.process_task(task_data, task_queue)
                    logger.info(f"Worker-{worker_id} completed task")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.exception(f"Worker-{worker_id} encountered error: {e}")

        logger.info(f"Worker-{worker_id} stopped")

    try:
        # 创建线程池并启动workers
        with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="Worker") as executor:
            # 提交所有worker任务
            futures = [executor.submit(worker_loop, i) for i in range(num_workers)]

            # 等待所有worker完成（或被中断）
            for future in as_completed(futures):
                try:
                    future.result()
                except KeyboardInterrupt:
                    stop_event.set()
                    break
                except Exception as e:
                    click.echo(f"❌ Worker error: {e}", err=True)

    except KeyboardInterrupt:
        click.echo("\n\n⏹ Stopping workers...")
        stop_event.set()
        click.echo("✓ All workers stopped")


@cli.command()
@click.option('--config', '-c', default='config/storage.yaml', type=click.Path(exists=True),
              help='BOS配置文件 (default: config/storage.yaml)')
@click.option('--interval', '-i', type=int, help='扫描间隔（秒）')
@click.option('--once', is_flag=True, help='只扫描一次后退出')
@click.option('--full-scan', is_flag=True, help='完整扫描（忽略增量位置）')
def scanner(config, interval, once, full_scan):
    """启动BOS Scanner服务

    扫描BOS上的新episode并发布到Redis队列。

    示例：
      lerobot-convert scanner -c config/storage.yaml --interval 120
    """
    import yaml
    from lerobot_converter.bos import BosClient, EpisodeScanner
    from lerobot_converter.redis import RedisClient, TaskQueue

    click.echo(f"📂 Loading config: {config}")

    # 初始化BOS客户端
    bos_client = BosClient(config)

    if not bos_client.test_connection():
        click.echo("❌ BOS connection failed", err=True)
        sys.exit(1)

    click.echo("✓ BOS connection successful")

    # 初始化 Redis 客户端（从配置文件）
    redis_client = RedisClient(config)

    if not redis_client.ping():
        click.echo("❌ Redis connection failed", err=True)
        sys.exit(1)

    click.echo("✓ Redis connection successful")

    # 创建TaskQueue和Scanner
    task_queue = TaskQueue(redis_client.client, redis_client.get_queue_name())
    scanner_instance = EpisodeScanner(bos_client, task_queue)

    # 处理full-scan标志
    if full_scan:
        scanner_config = bos_client.get_scanner_config()
        base_incremental_key = scanner_config.get('incremental_key', 'bos:last_scanned_key')
        # 生成与 scanner 相同的命名空间（基于 BOS 路径）
        import hashlib
        raw_data_prefix = bos_client.get_raw_data_prefix()
        converted_prefix = bos_client.get_converted_prefix()
        path_str = f"{raw_data_prefix}|{converted_prefix}"
        namespace = hashlib.md5(path_str.encode()).hexdigest()[:8]
        incremental_key = f"{base_incremental_key}:{namespace}"
        redis_client.client.delete(incremental_key)
        click.echo(f"✓ Full scan mode enabled (cleared key: {incremental_key})")

    # 获取扫描间隔
    scan_interval = interval if interval else bos_client.get_scanner_config().get('interval', 120)

    click.echo(f"\n🚀 Starting BOS Scanner")
    click.echo(f"Interval: {scan_interval}s")
    click.echo(f"Prefix: {bos_client.get_raw_data_prefix()}")
    click.echo("Press Ctrl+C to stop\n")

    try:
        scan_count = 0
        while True:
            scan_count += 1
            click.echo(f"[Scan #{scan_count}] Scanning BOS...")

            ready_episodes = scanner_instance.scan_and_filter()
            click.echo(f"✓ Found {len(ready_episodes)} ready episodes")

            # 发布到Redis
            from lerobot_converter.core.task import ConversionTask, AlignmentStrategy

            for ep_info in ready_episodes:
                task = ConversionTask(
                    episode_id=ep_info['episode_id'],
                    source='bos',
                    strategy=AlignmentStrategy.CHUNKING
                )
                task_queue.publish(task)
                click.echo(f"  → Published: {ep_info['episode_id']}")

            if once:
                click.echo("\n✓ Single scan completed")
                break

            import time
            click.echo(f"Waiting {scan_interval}s until next scan...\n")
            time.sleep(scan_interval)

    except KeyboardInterrupt:
        click.echo("\n\n✓ Scanner stopped")


@cli.command()
@click.option('--config', '-c', default='config/storage.yaml', type=click.Path(exists=True),
              help='Redis配置文件')
@click.option('--episode', '-e', required=True, help='Episode ID')
@click.option('--source', '-s', default='local', help='数据源ID')
@click.option('--strategy', type=click.Choice(['nearest', 'chunking', 'window']),
              default='chunking', help='对齐策略')
def publish(config, episode, source, strategy):
    """发布转换任务到Redis队列

    手动发布episode转换任务。

    示例：
      lerobot-convert publish -e episode_0001 -s robot_1 --strategy chunking
    """
    from lerobot_converter.redis import RedisClient, TaskQueue
    from lerobot_converter.core.task import ConversionTask, AlignmentStrategy

    click.echo(f"📂 Loading config: {config}")

    # 初始化 Redis 客户端（从配置文件）
    redis_client = RedisClient(config)

    if not redis_client.ping():
        click.echo("❌ Redis connection failed", err=True)
        sys.exit(1)

    click.echo("✓ Redis connection successful")

    task_queue = TaskQueue(redis_client.client, redis_client.get_queue_name())

    # 创建任务
    strategy_enum = AlignmentStrategy[strategy.upper()]
    task = ConversionTask(
        episode_id=episode,
        source=source,
        strategy=strategy_enum
    )

    # 发布任务
    task_queue.publish(task)

    click.echo(f"✓ Published task:")
    click.echo(f"  Episode: {episode}")
    click.echo(f"  Source: {source}")
    click.echo(f"  Strategy: {strategy}")
    click.echo(f"  Queue: {task_queue.queue_name}")


@cli.command()
@click.option('--config', '-c', default='config/storage.yaml', type=click.Path(exists=True),
              help='Redis配置文件')
@click.option('--refresh', '-r', type=int, default=5, help='刷新间隔（秒）')
def monitor(config, refresh):
    """监控Redis队列状态

    实时显示队列统计信息。

    示例：
      lerobot-convert monitor -c config/storage.yaml --refresh 5
    """
    import time
    from lerobot_converter.redis import RedisClient, TaskQueue

    click.echo(f"📂 Loading config: {config}")

    # 初始化 Redis 客户端（从配置文件）
    redis_client = RedisClient(config)

    if not redis_client.ping():
        click.echo("❌ Redis connection failed", err=True)
        sys.exit(1)

    click.echo("✓ Redis connection successful")

    task_queue = TaskQueue(redis_client.client, redis_client.get_queue_name())

    # 获取数据源列表
    sources = redis_client.get_sources()

    click.echo("\n🔍 Redis Queue Monitor")
    click.echo(f"Queue: {task_queue.queue_name}")
    click.echo(f"Refresh: {refresh}s")
    click.echo("Press Ctrl+C to stop\n")

    try:
        while True:
            # 获取统计信息
            pending = task_queue.get_pending_count()
            failed = task_queue.get_failed_count()

            # 获取各数据源的统计
            stats_lines = []
            for source in sources:
                stats = task_queue.get_stats(source)
                completed = stats['completed']
                failed_count = stats['failed']
                stats_lines.append(f"  {source}: ✓ {completed}  ✗ {failed_count}")

            # 清屏并显示
            click.clear()
            click.echo("="*60)
            click.echo(f"Queue Status (updated every {refresh}s)")
            click.echo("="*60)
            click.echo(f"Pending Tasks: {pending}")
            click.echo(f"Failed Tasks: {failed}")
            click.echo("\nSource Statistics:")
            for line in stats_lines:
                click.echo(line)
            click.echo("="*60)
            click.echo("\nPress Ctrl+C to exit")

            time.sleep(refresh)

    except KeyboardInterrupt:
        click.echo("\n\n✓ Monitor stopped")


if __name__ == '__main__':
    cli()
