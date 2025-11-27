"""Redis 客户端封装"""

import redis
import yaml
from pathlib import Path
from typing import Optional


class RedisClient:
    """Redis 客户端包装器

    职责：
    - Redis 连接管理
    - 配置加载
    """

    def __init__(self, config_path: str = 'config/redis_config.yaml'):
        """初始化 Redis 客户端

        Args:
            config_path: Redis 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.client = self._create_client()

    def _load_config(self, config_path: str) -> dict:
        """加载 Redis 配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            # 尝试从项目根目录查找
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / config_path

        with open(config_file, 'r') as f:
            return yaml.safe_load(f)

    def _create_client(self) -> redis.Redis:
        """创建 Redis 连接"""
        redis_conf = self.config['redis']
        return redis.Redis(
            host=redis_conf['host'],
            port=redis_conf['port'],
            db=redis_conf['db'],
            password=redis_conf.get('password'),
            decode_responses=True
        )

    def ping(self) -> bool:
        """测试 Redis 连接"""
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False

    def get_queue_name(self) -> str:
        """获取队列名称"""
        return self.config['redis']['queue_name']

    def get_sources(self) -> list:
        """获取数据源列表"""
        return self.config.get('sources', [])

    def get_worker_config(self) -> dict:
        """获取 Worker 配置"""
        return self.config.get('worker', {})

    def get_conversion_config(self) -> dict:
        """获取转换配置"""
        return self.config.get('conversion', {})

    def get_output_pattern(self) -> str:
        """获取输出路径模板"""
        return self.config.get('output', {}).get('pattern', './lerobot_datasets/{source}/{episode_id}_{strategy}')
