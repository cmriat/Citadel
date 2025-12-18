"""BOS (百度云对象存储) 客户端

封装 boto3 连接 BOS 的逻辑，提供配置管理和基本操作。
"""

import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BosClient:
    """BOS 客户端，管理与百度云对象存储的连接"""

    def __init__(self, config_path: str = 'config/bos_config.yaml'):
        """初始化 BOS 客户端

        Args:
            config_path: BOS 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.client = self._create_client()
        self.bucket = self.config['bos']['bucket']

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 替换环境变量
        bos_config = config['bos']
        bos_config['access_key'] = os.path.expandvars(bos_config['access_key'])
        bos_config['secret_key'] = os.path.expandvars(bos_config['secret_key'])

        # DEBUG: 检查密钥是否正确加载
        ak = bos_config['access_key']
        if ak.startswith("${"):
            logger.error("❌ CRITICAL: Environment variables BOS_ACCESS_KEY is NOT set! Using literal string.")
        else:
            logger.info(f"✓ Loaded Access Key: {ak[:6]}... (Length: {len(ak)})")

        return config

    def _create_client(self):
        """创建 boto3 S3 客户端连接到 BOS"""
        bos_config = self.config['bos']

        # 计算连接池大小：基于下载/上传并发数
        download_concurrent = bos_config.get('download', {}).get('concurrent', 4)
        upload_concurrent = bos_config.get('upload', {}).get('concurrent', 4)
        # 连接池大小 = 最大并发数 * 2 + 余量，确保足够
        max_pool_connections = max(download_concurrent, upload_concurrent) * 2 + 10

        client = boto3.client(
            's3',
            endpoint_url=bos_config['endpoint'],
            aws_access_key_id=bos_config['access_key'],
            aws_secret_access_key=bos_config['secret_key'],
            region_name=bos_config.get('region', 'bj'),
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},  # 强制使用 path style
                max_pool_connections=max_pool_connections  # 增加连接池大小
            )
        )

        logger.info(f"BOS client created with max_pool_connections={max_pool_connections}")
        return client

    def test_connection(self) -> bool:
        """测试 BOS 连接是否正常

        Returns:
            bool: 连接是否成功
        """
        try:
            # 尝试列出 bucket，验证连接和权限
            self.client.head_bucket(Bucket=self.bucket)
            logger.info(f"✓ Successfully connected to BOS bucket: {self.bucket}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"✗ Bucket '{self.bucket}' not found")
            elif error_code == '403':
                logger.error(f"✗ Access denied to bucket '{self.bucket}'")
            else:
                logger.error(f"✗ Connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False

    def list_objects(
        self,
        prefix: str = '',
        max_keys: int = 1000,
        start_after: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出对象

        Args:
            prefix: 对象前缀（路径）
            max_keys: 最多返回的对象数量
            start_after: 从这个 key 之后开始列出（用于增量扫描）

        Returns:
            Dict: boto3 list_objects_v2 的响应
        """
        params = {
            'Bucket': self.bucket,
            'Prefix': prefix,
            'MaxKeys': max_keys
        }

        if start_after:
            params['StartAfter'] = start_after

        try:
            response = self.client.list_objects_v2(**params)
            return response
        except ClientError as e:
            logger.error(f"Failed to list objects with prefix '{prefix}': {e}")
            raise

    def object_exists(self, key: str) -> bool:
        """检查对象是否存在

        Args:
            key: 对象 key

        Returns:
            bool: 对象是否存在
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def get_object_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """获取对象元数据

        Args:
            key: 对象 key

        Returns:
            Dict: 对象元数据，如果对象不存在返回 None
        """
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            return {
                'last_modified': response['LastModified'],
                'content_length': response['ContentLength'],
                'etag': response['ETag']
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise

    def get_raw_data_prefix(self) -> str:
        """获取原始数据路径前缀

        Returns:
            str: 原始数据前缀
        """
        return self.config['bos']['paths']['raw_data']

    def get_converted_prefix(self) -> str:
        """获取转换后数据路径前缀

        Returns:
            str: 转换后数据前缀
        """
        return self.config['bos']['paths']['converted']

    def get_task_name(self) -> str:
        """获取任务名称（用于目录重组织）

        Returns:
            str: 任务名称，默认为 'quad_arm_task'
        """
        return self.config['bos'].get('task_name', 'quad_arm_task')

    def get_scanner_config(self) -> Dict[str, Any]:
        """获取扫描器配置

        Returns:
            Dict: 扫描器配置
        """
        return self.config['bos']['scanner']

    def get_validation_config(self) -> Dict[str, Any]:
        """获取验证配置

        Returns:
            Dict: 验证配置
        """
        return self.config['bos']['validation']

    def get_download_config(self) -> Dict[str, Any]:
        """获取下载配置

        Returns:
            Dict: 下载配置
        """
        return self.config['bos']['download']

    def get_upload_config(self) -> Dict[str, Any]:
        """获取上传配置

        Returns:
            Dict: 上传配置
        """
        return self.config['bos']['upload']

    def get_redis_config(self) -> Dict[str, Any]:
        """获取 Redis 配置

        Returns:
            Dict: Redis 配置
        """
        return self.config['redis']
