"""Action Chunking 对齐策略"""

import numpy as np
from typing import Dict, List, Tuple
from .base import BaseAligner


class ChunkingAligner(BaseAligner):
    """Action Chunking 对齐策略 - 数据利用率最高（推荐）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.chunk_size = config.get('chunk_size', 10)
        self.padding_mode = config.get('padding_mode', 'repeat')

    def align(
        self,
        base_timestamps: np.ndarray,
        arm_data: Dict[str, Dict],
        synced_camera_frames: List[Dict]
    ) -> List[Dict]:
        """执行 Action Chunking 对齐"""
        aligned_frames = []

        for frame_idx, camera_frame in enumerate(synced_camera_frames):
            img_ts = camera_frame['timestamp']

            # 1. 当前 observation (最近邻)
            # 对齐 slave 臂 (observation.state.slave)
            left_slave_idx = self._find_nearest(arm_data['left_slave']['timestamps'], img_ts)
            right_slave_idx = self._find_nearest(arm_data['right_slave']['timestamps'], img_ts)

            obs_slave = self._concat_arms(
                arm_data['left_slave']['states'][left_slave_idx],
                arm_data['right_slave']['states'][right_slave_idx]
            )  # (14,)

            # 对齐 master 臂 (observation.state.master)
            left_master_idx = self._find_nearest(arm_data['left_master']['timestamps'], img_ts)
            right_master_idx = self._find_nearest(arm_data['right_master']['timestamps'], img_ts)

            obs_master = self._concat_arms(
                arm_data['left_master']['states'][left_master_idx],
                arm_data['right_master']['states'][right_master_idx]
            )  # (14,)

            # 2. 未来 chunk_size 步的 action chunk
            # 使用 master 臂的未来动作
            left_action_chunk = self._extract_action_chunk(
                arm_data['left_master'],
                left_master_idx
            )  # (chunk_size, 7)

            right_action_chunk = self._extract_action_chunk(
                arm_data['right_master'],
                right_master_idx
            )  # (chunk_size, 7)

            # 拼接左右臂 action
            action = np.concatenate([left_action_chunk, right_action_chunk], axis=1)  # (chunk_size, 14)

            # 3. 构造帧数据
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

    def _extract_action_chunk(self, arm_data: Dict, start_idx: int) -> np.ndarray:
        """
        提取一个臂的 action chunk

        Args:
            arm_data: 单个臂的数据 {'timestamps': ..., 'states': ...}
            start_idx: 起始索引

        Returns:
            action_chunk: (chunk_size, 7)
        """
        states = arm_data['states']
        end_idx = start_idx + self.chunk_size

        if end_idx <= len(states):
            # 完整的 chunk
            chunk = states[start_idx:end_idx]
        else:
            # Episode 末尾，需要 padding
            chunk = states[start_idx:]
            chunk = self._pad_chunk(chunk)

        return chunk.astype(np.float32)

    def _pad_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """
        处理 episode 末尾的 padding

        Args:
            chunk: 不完整的 chunk (N, 7), N < chunk_size

        Returns:
            padded_chunk: (chunk_size, 7)
        """
        if len(chunk) >= self.chunk_size:
            return chunk[:self.chunk_size]

        if self.padding_mode == 'repeat':
            # 重复最后一帧
            padding = np.repeat(chunk[-1:], self.chunk_size - len(chunk), axis=0)
            return np.vstack([chunk, padding])
        elif self.padding_mode == 'zeros':
            # 填充零
            padding = np.zeros((self.chunk_size - len(chunk), chunk.shape[1]), dtype=np.float32)
            return np.vstack([chunk, padding])
        else:
            raise ValueError(f"Unknown padding_mode: {self.padding_mode}")

    def get_action_shape(self) -> Tuple:
        """返回 action shape: (chunk_size, 14)"""
        return (self.chunk_size, 14)
