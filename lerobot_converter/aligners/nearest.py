"""最近邻对齐策略"""

import numpy as np
from typing import Dict, List, Tuple
from .base import BaseAligner


class NearestAligner(BaseAligner):
    """最近邻对齐策略 - 简单直接，快速验证"""

    def align(
        self,
        base_timestamps: np.ndarray,
        arm_data: Dict[str, Dict],
        synced_camera_frames: List[Dict]
    ) -> List[Dict]:
        """执行最近邻对齐"""
        aligned_frames = []
        tolerance_ns = self.tolerance_ms * 1e6

        for frame_idx, camera_frame in enumerate(synced_camera_frames):
            img_ts = camera_frame['timestamp']

            # 1. 对齐 slave 臂 (observation.state.slave)
            left_slave_idx = self._find_nearest(arm_data['left_slave']['timestamps'], img_ts)
            right_slave_idx = self._find_nearest(arm_data['right_slave']['timestamps'], img_ts)

            # 检查时间容差
            if abs(arm_data['left_slave']['timestamps'][left_slave_idx] - img_ts) > tolerance_ns:
                continue

            obs_slave = self._concat_arms(
                arm_data['left_slave']['states'][left_slave_idx],
                arm_data['right_slave']['states'][right_slave_idx]
            )  # (14,)

            # 2. 对齐 master 臂 (observation.state.master)
            left_master_idx = self._find_nearest(arm_data['left_master']['timestamps'], img_ts)
            right_master_idx = self._find_nearest(arm_data['right_master']['timestamps'], img_ts)

            obs_master = self._concat_arms(
                arm_data['left_master']['states'][left_master_idx],
                arm_data['right_master']['states'][right_master_idx]
            )  # (14,)

            # 3. Action: 使用 master 臂的当前状态（单步）
            action = self._concat_arms(
                arm_data['left_master']['states'][left_master_idx],
                arm_data['right_master']['states'][right_master_idx]
            )  # (14,)

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

    def get_action_shape(self) -> Tuple:
        """返回 action shape: (14,)"""
        return (14,)
