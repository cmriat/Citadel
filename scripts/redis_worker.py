#!/usr/bin/env python3
"""Redis Worker 服务 - 监听队列并处理转换任务"""

import redis
import json
import time
import argparse
import yaml
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.pipeline.converter import LeRobotConverter
from lerobot_converter.pipeline.config import load_config


class RedisWorker:
    """Redis Worker - 处理转换任务队列"""

    def __init__(self, config_path: str):
        """
        Args:
            config_path: Redis 配置文件路径
        """
        # 加载配置
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # 连接 Redis
        self.redis_client = redis.Redis(
            host=self.config['redis']['host'],
            port=self.config['redis']['port'],
            db=self.config['redis']['db'],
            password=self.config['redis'].get('password'),
            decode_responses=True
        )

        # 配置参数
        self.queue_name = self.config['redis']['queue_name']
        self.max_workers = self.config['worker']['max_workers']
        self.poll_interval = self.config['worker']['poll_interval']
        self.output_pattern = self.config['output']['pattern']
        self.default_strategy = self.config['conversion']['strategy']
        self.config_template = self.config['conversion']['config_template']

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        print(f"✓ Connected to Redis: {self.config['redis']['host']}:{self.config['redis']['port']}")
        print(f"✓ Queue: {self.queue_name}")
        print(f"✓ Max workers: {self.max_workers}")

    def is_processed(self, source: str, episode_id: str) -> bool:
        """
        检查是否已处理过

        Args:
            source: 数据源ID
            episode_id: Episode ID

        Returns:
            True if已处理
        """
        key = f"lerobot:processed:{source}:{episode_id}"
        return self.redis_client.exists(key) > 0

    def mark_processed(self, source: str, episode_id: str, ttl_days: int = 30):
        """
        标记为已处理

        Args:
            source: 数据源ID
            episode_id: Episode ID
            ttl_days: 保留天数
        """
        key = f"lerobot:processed:{source}:{episode_id}"
        self.redis_client.setex(key, ttl_days * 86400, "1")

    def record_stats(self, source: str, status: str):
        """
        记录统计信息

        Args:
            source: 数据源ID
            status: 状态 (completed/failed)
        """
        # 增加计数
        self.redis_client.incr(f"lerobot:stats:{source}:{status}")

        # 记录最后更新时间
        self.redis_client.set(
            f"lerobot:stats:{source}:last_update",
            int(time.time())
        )

    def save_episode_info(self, source: str, episode_id: str, status: str, error: str = None):
        """
        保存 episode 处理信息

        Args:
            source: 数据源ID
            episode_id: Episode ID
            status: 状态
            error: 错误信息（如果有）
        """
        key = f"lerobot:episode:{source}:{episode_id}"
        data = {
            'status': status,
            'timestamp': int(time.time())
        }
        if error:
            data['error'] = error

        self.redis_client.hset(key, mapping=data)
        # 设置过期时间
        self.redis_client.expire(key, 86400 * 7)  # 7天后删除

    def process_task(self, task: dict):
        """
        处理单个转换任务

        Args:
            task: 任务信息
        """
        episode_id = task['episode_id']
        source = task['source']
        strategy = task.get('strategy', self.default_strategy)

        # 检查是否已处理
        if self.is_processed(source, episode_id):
            print(f"⊘ Already processed: {source}/{episode_id}")
            return

        print(f"🔄 Processing: {source}/{episode_id} (strategy: {strategy})")

        try:
            # 生成输出路径
            output_path = self.output_pattern.format(
                source=source,
                episode_id=episode_id,
                strategy=strategy
            )

            # 加载转换配置
            converter_config = load_config(self.config_template)

            # 修改输出路径
            converter_config['output']['base_path'] = output_path
            converter_config['output']['dataset_name'] = f"{source}_{episode_id}"

            # 创建转换器
            converter = LeRobotConverter(converter_config)

            # 执行转换
            converter.convert(episode_id=episode_id)

            # 标记完成
            self.mark_processed(source, episode_id)
            self.record_stats(source, 'completed')
            self.save_episode_info(source, episode_id, 'completed')

            print(f"✓ Completed: {source}/{episode_id}")

        except Exception as e:
            # 记录失败
            error_msg = str(e)
            self.record_stats(source, 'failed')
            self.save_episode_info(source, episode_id, 'failed', error_msg)

            print(f"✗ Failed: {source}/{episode_id} - {error_msg}")

            # 失败任务移到失败队列
            self.redis_client.lpush(
                f"{self.queue_name}:failed",
                json.dumps(task)
            )

    def run(self):
        """运行 Worker（主循环）"""
        print(f"\n🚀 Worker started, waiting for tasks...")
        print(f"Press Ctrl+C to stop\n")

        try:
            while True:
                # 阻塞等待任务（timeout 避免无限阻塞）
                result = self.redis_client.brpop(self.queue_name, timeout=self.poll_interval)

                if result:
                    _, task_json = result
                    task = json.loads(task_json)

                    # 提交到线程池处理
                    self.executor.submit(self.process_task, task)

        except KeyboardInterrupt:
            print("\n\n⚠️  Shutting down...")
            self.executor.shutdown(wait=True)
            print("✓ Worker stopped\n")


def main():
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
        worker = RedisWorker(args.config)
        worker.run()
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
