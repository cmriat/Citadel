"""时间窗口平均对齐策略"""

import numpy as np
from typing import Dict, List, Tuple
from .base import BaseAligner


class WindowAligner(BaseAligner):
    """时间窗口平均对齐策略 - 平滑噪声，降噪"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.window_ms = config.get('window_ms', 20)
        self.aggregation = config.get('aggregation', 'mean')

    def align(
        self,
        base_timestamps: np.ndarray,
        arm_data: Dict[str, Dict],
        synced_camera_frames: List[Dict]
    ) -> List[Dict]:
        """执行时间窗口平均对齐"""
        aligned_frames = []
        window_ns = self.window_ms * 1e6  # 转为纳秒

        for frame_idx, camera_frame in enumerate(synced_camera_frames):
            img_ts = camera_frame['timestamp']

            # 定义时间窗口
            window_start = img_ts - window_ns
            window_end = img_ts + window_ns

            # 1. 对齐 slave 臂 (observation.state.slave)
            left_slave_states = self._aggregate_in_window(
                arm_data['left_slave']['timestamps'],
                arm_data['left_slave']['states'],
                window_start,
                window_end
            )

            right_slave_states = self._aggregate_in_window(
                arm_data['right_slave']['timestamps'],
                arm_data['right_slave']['states'],
                window_start,
                window_end
            )

            if left_slave_states is None or right_slave_states is None:
                continue  # 窗口内没有数据

            obs_slave = self._concat_arms(left_slave_states, right_slave_states)  # (14,)

            # 2. 对齐 master 臂 (observation.state.master)
            left_master_states = self._aggregate_in_window(
                arm_data['left_master']['timestamps'],
                arm_data['left_master']['states'],
                window_start,
                window_end
            )

            right_master_states = self._aggregate_in_window(
                arm_data['right_master']['timestamps'],
                arm_data['right_master']['states'],
                window_start,
                window_end
            )

            if left_master_states is None or right_master_states is None:
                continue

            obs_master = self._concat_arms(left_master_states, right_master_states)  # (14,)

            # 3. Action: 使用 master 臂的聚合结果（单步，平滑后）
            action = self._concat_arms(left_master_states, right_master_states)  # (14,)

            # 4. 构造帧数据
            frame_data = {
                'timestamp': img_ts,
                'observation.state.slave': obs_slave,
                'observation.state.master': obs_master,
                'observation.images.cam_left': camera_frame.get('cam_left'),
                'observation.images.cam_right': camera_frame.get('cam_right'),
                'observation.images.cam_head': camera_frame.get('cam_head'),
                'action': action,
                'frame_index': frame_idx
            }

            aligned_frames.append(frame_data)

        return aligned_frames

    def _aggregate_in_window(
        self,
        timestamps: np.ndarray,
        states: np.ndarray,
        window_start: int,
        window_end: int
    ) -> np.ndarray:
        """
        在时间窗口内聚合数据

        Args:
            timestamps: 时间戳数组
            states: 状态数组 (N, 7)
            window_start: 窗口开始时间（纳秒）
            window_end: 窗口结束时间（纳秒）

        Returns:
            aggregated_state: (7,) 聚合后的状态
        """
        # 找到窗口内的所有索引
        mask = (timestamps >= window_start) & (timestamps <= window_end)
        window_states = states[mask]

        if len(window_states) == 0:
            return None

        # 聚合
        if self.aggregation == 'mean':
            return window_states.mean(axis=0).astype(np.float32)
        elif self.aggregation == 'median':
            return np.median(window_states, axis=0).astype(np.float32)
        else:
            raise ValueError(f"Unknown aggregation method: {self.aggregation}")

    def get_action_shape(self) -> Tuple:
        """返回 action shape: (14,)"""
        return (14,)
