"""配置加载和验证"""

import yaml
from pathlib import Path
from typing import Dict


def load_config(config_path: str) -> Dict:
    """
    加载 YAML 配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # 验证配置
    validate_config(config)

    return config


def validate_config(config: Dict):
    """
    验证配置文件的完整性

    Args:
        config: 配置字典

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

    if strategy == 'window':
        if 'window_ms' not in config['alignment']:
            raise ValueError("window_ms is required for window strategy")

    # 验证输入路径
    input_data_path = Path(config['input']['data_path'])
    input_images_path = Path(config['input']['images_path'])

    if not input_data_path.exists():
        raise FileNotFoundError(f"Data path not found: {input_data_path}")

    if not input_images_path.exists():
        raise FileNotFoundError(f"Images path not found: {input_images_path}")

    print("✓ Config validation passed")


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
