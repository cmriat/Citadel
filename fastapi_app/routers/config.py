"""配置管理 API"""

import os
import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException

from ..schemas.models import (
    AppConfig, ApiResponse, TestBosResponse
)
from ..services.scanner_service import scanner_service
from ..services.worker_service import worker_service

logger = logging.getLogger(__name__)
router = APIRouter()

# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "web_config.yaml"

# 内存中的配置
_current_config: Optional[AppConfig] = None


def _load_config_from_file() -> AppConfig:
    """从文件加载配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            data = yaml.safe_load(f)
            return AppConfig(**data) if data else AppConfig()
    return AppConfig()


def _save_config_to_file(config: AppConfig):
    """保存配置到文件"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        # 使用 mode='json' 确保枚举值转换为字符串
        yaml.dump(config.model_dump(mode='json'), f, default_flow_style=False, allow_unicode=True)


def get_current_config() -> AppConfig:
    """获取当前配置"""
    global _current_config
    if _current_config is None:
        _current_config = _load_config_from_file()
    return _current_config


@router.get("", response_model=AppConfig)
async def get_config():
    """获取当前配置"""
    return get_current_config()


@router.put("", response_model=ApiResponse)
async def update_config(config: AppConfig):
    """更新配置"""
    global _current_config

    try:
        # 更新内存中的配置
        _current_config = config

        # 保存到文件
        _save_config_to_file(config)

        # 同步到服务
        config_dict = config.model_dump()
        scanner_service.set_config(config_dict)
        worker_service.set_config(config_dict)

        logger.info("Config updated successfully")
        return ApiResponse(success=True, message="配置已保存")

    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-bos", response_model=TestBosResponse)
async def test_bos_connection(config: Optional[AppConfig] = None):
    """测试 BOS 连接

    如果传入 config 参数，使用传入的配置测试；
    否则使用当前保存的配置。
    """
    if config is None:
        config = get_current_config()

    # 调试日志
    logger.info(f"Testing BOS connection with endpoint={config.bos.endpoint}, bucket={config.bos.bucket}")
    logger.info(f"Access key length: {len(config.bos.access_key)}, Secret key length: {len(config.bos.secret_key)}")

    try:
        import boto3
        from botocore.config import Config as BotoConfig

        # 创建 S3 客户端
        client = boto3.client(
            's3',
            endpoint_url=config.bos.endpoint,
            aws_access_key_id=config.bos.access_key,
            aws_secret_access_key=config.bos.secret_key,
            region_name=config.bos.region,
            config=BotoConfig(signature_version='s3v4')
        )

        # 测试 bucket 是否存在
        bucket_exists = False
        try:
            client.head_bucket(Bucket=config.bos.bucket)
            bucket_exists = True
        except Exception as e:
            logger.warning(f"Bucket check failed: {e}")

        # 测试 raw_data 路径
        raw_data_exists = False
        if bucket_exists and config.paths.raw_data:
            try:
                response = client.list_objects_v2(
                    Bucket=config.bos.bucket,
                    Prefix=config.paths.raw_data,
                    MaxKeys=1
                )
                raw_data_exists = 'Contents' in response
            except Exception as e:
                logger.warning(f"Raw data path check failed: {e}")

        # 测试 converted 路径
        converted_exists = False
        if bucket_exists and config.paths.converted:
            try:
                response = client.list_objects_v2(
                    Bucket=config.bos.bucket,
                    Prefix=config.paths.converted,
                    MaxKeys=1
                )
                # converted 目录可能为空，只要不报错就算存在
                converted_exists = True
            except Exception as e:
                logger.warning(f"Converted path check failed: {e}")

        if bucket_exists:
            message = "连接成功"
            if raw_data_exists:
                message += "，原始数据路径有效"
            else:
                message += "，但原始数据路径为空或不存在"
        else:
            message = "连接失败：无法访问 Bucket"

        return TestBosResponse(
            success=bucket_exists,
            message=message,
            bucket_exists=bucket_exists,
            raw_data_exists=raw_data_exists,
            converted_exists=converted_exists
        )

    except Exception as e:
        logger.error(f"BOS connection test failed: {e}")
        return TestBosResponse(
            success=False,
            message=f"连接失败: {str(e)}",
            bucket_exists=False,
            raw_data_exists=False,
            converted_exists=False
        )
