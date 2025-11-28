"""文件读写工具模块"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from PIL import Image


def load_parquet(file_path: str) -> pd.DataFrame:
    """加载 Parquet 文件"""
    return pd.read_parquet(file_path)


def load_json(file_path: str) -> Dict:
    """加载 JSON 文件"""
    with open(file_path, 'r') as f:
        return json.load(f)


def save_json(data: Dict, file_path: str):
    """保存 JSON 文件"""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def load_joint_data(file_path: str, joints_dim: int = 7) -> Tuple[np.ndarray, np.ndarray]:
    """
    加载关节数据

    Args:
        file_path: Parquet 文件路径
        joints_dim: 关节维度（默认 7: joint1-6 + eef_gripper）

    Returns:
        timestamps: 时间戳数组（纳秒）
        states: 关节状态数组 (N, joints_dim)
    """
    df = load_parquet(file_path)

    # 提取时间戳
    timestamps = (df['timestamp_sec'].values * 1e9 +
                  df['timestamp_nanosec'].values).astype(np.int64)

    # 提取关节位置 (joint1-6 + eef_gripper_joint_pos)
    joint_cols = [f'joint{i}_pos' for i in range(1, 7)] + ['eef_gripper_joint_pos']
    states = df[joint_cols].values.astype(np.float32)

    # 处理 NaN 值（前向填充）
    if np.any(np.isnan(states)):
        df_states = pd.DataFrame(states)
        df_states = df_states.fillna(method='ffill').fillna(method='bfill')
        states = df_states.values.astype(np.float32)

    return timestamps, states


def load_image(image_path: str) -> np.ndarray:
    """
    加载图像

    Returns:
        image: (H, W, 3) RGB 图像
    """
    img = Image.open(image_path)
    return np.array(img)


def get_image_list(camera_dir: str) -> List[str]:
    """
    获取相机目录下的所有图像文件

    Returns:
        排序后的图像文件路径列表
    """
    camera_path = Path(camera_dir)
    images = sorted(camera_path.glob('*.jpg'))
    return [str(img) for img in images]
