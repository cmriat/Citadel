"""相机同步和降采样工具"""

import numpy as np
from typing import Dict, List
from .timestamp import find_nearest, downsample_indices


def sync_cameras(
    base_camera_timestamps: np.ndarray,
    all_camera_data: Dict[str, Dict],
    tolerance_ms: float = 20
) -> List[Dict]:
    """
    将所有相机同步到基准相机的时间轴

    Args:
        base_camera_timestamps: 基准相机的时间戳数组
        all_camera_data: 所有相机的数据
            {
                'cam_left': {'timestamps': [...], 'images': [...]},
                'cam_right': {...},
                'cam_head': {...}
            }
        tolerance_ms: 时间容差（毫秒）

    Returns:
        同步后的帧列表，每个元素包含所有相机在该时刻的信息
    """
    synced_frames = []
    tolerance_ns = tolerance_ms * 1e6

    for base_ts in base_camera_timestamps:
        frame_data = {'timestamp': base_ts}

        # 同步所有相机
        all_valid = True
        for cam_name, cam_data in all_camera_data.items():
            cam_timestamps = cam_data['timestamps']
            nearest_idx = find_nearest(cam_timestamps, base_ts)

            # 检查时间差
            time_diff = abs(cam_timestamps[nearest_idx] - base_ts)
            if time_diff > tolerance_ns:
                all_valid = False
                break

            frame_data[cam_name] = {
                'index': nearest_idx,
                'timestamp': cam_timestamps[nearest_idx],
                'time_diff_ms': time_diff / 1e6
            }

        if all_valid:
            synced_frames.append(frame_data)

    return synced_frames


def downsample_camera(
    high_freq_timestamps: np.ndarray,
    low_freq_timestamps: np.ndarray
) -> List[int]:
    """
    将高频相机降采样到低频基准

    Args:
        high_freq_timestamps: 高频相机时间戳（如 30Hz 的 cam_head）
        low_freq_timestamps: 低频基准时间戳（如 25Hz 的 cam_left）

    Returns:
        高频时间戳中被选中的索引列表
    """
    return downsample_indices(high_freq_timestamps, low_freq_timestamps)


def validate_camera_sync(synced_frames: List[Dict], camera_names: List[str]) -> Dict:
    """
    验证相机同步质量

    Returns:
        同步质量报告
    """
    if not synced_frames:
        return {'status': 'failed', 'reason': 'No synced frames'}

    # 计算每个相机的平均时间差
    time_diffs = {cam: [] for cam in camera_names}

    for frame in synced_frames:
        for cam in camera_names:
            if cam in frame:
                time_diffs[cam].append(frame[cam]['time_diff_ms'])

    report = {
        'status': 'passed',
        'total_frames': len(synced_frames),
        'camera_stats': {}
    }

    for cam, diffs in time_diffs.items():
        if diffs:
            report['camera_stats'][cam] = {
                'mean_diff_ms': float(np.mean(diffs)),
                'max_diff_ms': float(np.max(diffs)),
                'std_diff_ms': float(np.std(diffs))
            }

    return report
