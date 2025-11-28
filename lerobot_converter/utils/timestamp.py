"""时间戳处理和对齐工具"""

import numpy as np
from typing import List


def find_nearest(timestamps: np.ndarray, target: int) -> int:
    """
    找到最接近目标时间戳的索引

    Args:
        timestamps: 时间戳数组（纳秒）
        target: 目标时间戳（纳秒）

    Returns:
        最近的索引
    """
    return int(np.argmin(np.abs(timestamps - target)))


def find_in_window(timestamps: np.ndarray, window_start: int, window_end: int) -> np.ndarray:
    """
    找到时间窗口内的所有索引

    Args:
        timestamps: 时间戳数组（纳秒）
        window_start: 窗口开始时间（纳秒）
        window_end: 窗口结束时间（纳秒）

    Returns:
        窗口内的索引数组
    """
    mask = (timestamps >= window_start) & (timestamps <= window_end)
    return np.where(mask)[0]


def check_time_tolerance(timestamps: np.ndarray, target: int, tolerance_ms: float) -> bool:
    """
    检查最近的时间戳是否在容差范围内

    Args:
        timestamps: 时间戳数组（纳秒）
        target: 目标时间戳（纳秒）
        tolerance_ms: 容差（毫秒）

    Returns:
        是否在容差范围内
    """
    nearest_idx = find_nearest(timestamps, target)
    diff_ms = abs(timestamps[nearest_idx] - target) / 1e6
    return diff_ms <= tolerance_ms


def compute_frequency(timestamps: np.ndarray) -> float:
    """
    计算采样频率

    Args:
        timestamps: 时间戳数组（纳秒）

    Returns:
        频率 (Hz)
    """
    if len(timestamps) < 2:
        return 0.0

    intervals = np.diff(timestamps) / 1e9  # 转为秒
    avg_interval = np.mean(intervals)
    return 1.0 / avg_interval if avg_interval > 0 else 0.0


def downsample_indices(high_freq_timestamps: np.ndarray,
                        low_freq_timestamps: np.ndarray) -> List[int]:
    """
    将高频时间戳降采样到低频时间戳

    Args:
        high_freq_timestamps: 高频时间戳数组
        low_freq_timestamps: 低频时间戳数组（基准）

    Returns:
        高频时间戳中被选中的索引列表
    """
    selected_indices = []
    for target_ts in low_freq_timestamps:
        idx = find_nearest(high_freq_timestamps, target_ts)
        selected_indices.append(idx)
    return selected_indices
