"""配置加载和验证"""

import logging
import yaml
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def load_config(config_path: str, skip_path_validation: bool = False) -> Dict:
    """
    加载 YAML 配置文件

    Args:
        config_path: 配置文件路径
        skip_path_validation: 是否跳过输入路径验证（BOS Worker 场景使用）

    Returns:
        配置字典
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # 验证配置
    validate_config(config, skip_path_validation=skip_path_validation)

    return config


def validate_config(config: Dict, skip_path_validation: bool = False):
    """
    验证配置文件的完整性

    Args:
        config: 配置字典
        skip_path_validation: 是否跳过输入路径验证（BOS Worker 场景使用）

    Raises:
        ValueError: 配置无效时
    """
    # 检查必需的顶层字段
    required_fields = ['robot', 'cameras', 'input', 'output', 'alignment']
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field in config: {field}")

    # 验证 robot 配置
    if 'arms' not in config['robot']:
        raise ValueError("Missing 'arms' in robot config")

    if len(config['robot']['arms']) == 0:
        raise ValueError("At least one arm must be configured")

    # 验证 cameras 配置
    if len(config['cameras']) == 0:
        raise ValueError("At least one camera must be configured")

    # 检查基准相机
    has_base_camera = any(cam.get('role') == 'base' for cam in config['cameras'])
    if not has_base_camera:
        raise ValueError("At least one camera must have role='base'")

    # 验证 alignment 策略
    strategy = config['alignment'].get('strategy')
    valid_strategies = ['nearest', 'chunking', 'window']
    if strategy not in valid_strategies:
        raise ValueError(f"Invalid alignment strategy: {strategy}. "
                         f"Must be one of {valid_strategies}")

    # 验证策略特定参数
    if strategy == 'chunking':
        if 'chunk_size' not in config['alignment']:
            raise ValueError("chunk_size is required for chunking strategy")
        chunk_size = config['alignment']['chunk_size']
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError(f"chunk_size must be a positive integer, got: {chunk_size}")

    if strategy == 'window':
        if 'window_ms' not in config['alignment']:
            raise ValueError("window_ms is required for window strategy")
        window_ms = config['alignment']['window_ms']
        if not isinstance(window_ms, (int, float)) or window_ms <= 0:
            raise ValueError(f"window_ms must be a positive number, got: {window_ms}")

    # 验证 tolerance_ms（所有策略都需要）
    tolerance_ms = config['alignment'].get('tolerance_ms')
    if tolerance_ms is not None:
        if not isinstance(tolerance_ms, (int, float)) or tolerance_ms <= 0:
            raise ValueError(f"tolerance_ms must be a positive number, got: {tolerance_ms}")

    # 验证 video 配置（如果存在）
    if 'video' in config:
        fps = config['video'].get('fps')
        if fps is not None:
            if not isinstance(fps, (int, float)) or fps <= 0:
                raise ValueError(f"video.fps must be a positive number, got: {fps}")
        codec = config['video'].get('codec')
        if codec is not None and not isinstance(codec, str):
            raise ValueError(f"video.codec must be a string, got: {type(codec).__name__}")

    # 验证 filtering 配置（如果存在）
    if 'filtering' in config:
        min_frames = config['filtering'].get('min_frames')
        if min_frames is not None:
            if not isinstance(min_frames, int) or min_frames < 0:
                raise ValueError(f"filtering.min_frames must be a non-negative integer, got: {min_frames}")
        max_time_gap_ms = config['filtering'].get('max_time_gap_ms')
        if max_time_gap_ms is not None:
            if not isinstance(max_time_gap_ms, (int, float)) or max_time_gap_ms <= 0:
                raise ValueError(f"filtering.max_time_gap_ms must be a positive number, got: {max_time_gap_ms}")

    # 验证输入路径（可选跳过，用于 BOS Worker 动态设置路径的场景）
    if not skip_path_validation:
        input_data_path = Path(config['input']['data_path'])
        input_images_path = Path(config['input']['images_path'])

        if not input_data_path.exists():
            raise FileNotFoundError(f"Data path not found: {input_data_path}")

        if not input_images_path.exists():
            raise FileNotFoundError(f"Images path not found: {input_images_path}")

    logger.debug("Config validation passed")


def get_arm_config(config: Dict, arm_name: str) -> Dict:
    """
    获取指定臂的配置

    Args:
        config: 配置字典
        arm_name: 臂名称

    Returns:
        臂配置字典
    """
    for arm in config['robot']['arms']:
        if arm['name'] == arm_name:
            return arm

    raise ValueError(f"Arm not found in config: {arm_name}")


def get_camera_config(config: Dict, camera_name: str) -> Dict:
    """
    获取指定相机的配置

    Args:
        config: 配置字典
        camera_name: 相机名称

    Returns:
        相机配置字典
    """
    for cam in config['cameras']:
        if cam['name'] == camera_name:
            return cam

    raise ValueError(f"Camera not found in config: {camera_name}")


def get_base_camera_name(config: Dict) -> str:
    """
    获取基准相机名称

    Args:
        config: 配置字典

    Returns:
        基准相机名称
    """
    for cam in config['cameras']:
        if cam.get('role') == 'base':
            return cam['name']

    raise ValueError("No base camera found in config")
