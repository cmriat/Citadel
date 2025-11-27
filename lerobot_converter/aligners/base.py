"""时间对齐策略的抽象基类"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
import numpy as np


class BaseAligner(ABC):
    """时间对齐策略的抽象基类"""

    def __init__(self, config: Dict):
        """
        Args:
            config: alignment 配置字典
        """
        self.config = config
        self.tolerance_ms = config.get('tolerance_ms', 20)

    @abstractmethod
    def align(
        self,
        base_timestamps: np.ndarray,
        arm_data: Dict[str, Dict],
        synced_camera_frames: List[Dict]
    ) -> List[Dict]:
        """
        执行时间对齐

        Args:
            base_timestamps: 基准相机时间戳（如 cam_left 的时间戳）
            arm_data: 四臂数据字典
                {
                    'left_slave': {'timestamps': array, 'states': array},
                    'left_master': {'timestamps': array, 'states': array},
                    'right_slave': {...},
                    'right_master': {...}
                }
            synced_camera_frames: 已同步的相机帧列表
                [
                    {
                        'timestamp': int,
                        'cam_left': {'index': int, 'timestamp': int},
                        'cam_right': {...},
                        'cam_head': {...}
                    },
                    ...
                ]

        Returns:
            aligned_frames: 对齐后的帧列表
                [
                    {
                        'timestamp': int,
                        'observation.state.slave': (14,),
                        'observation.state.master': (14,),
                        'observation.images.cam_left': {'index': int, ...},
                        'observation.images.cam_right': {...},
                        'observation.images.cam_head': {...},
                        'action': (14,) or (chunk_size, 14),
                        'frame_index': int
                    },
                    ...
                ]
        """
        pass

    @abstractmethod
    def get_action_shape(self) -> Tuple:
        """返回 action 的 shape，用于生成 meta/info.json"""
        pass

    def _find_nearest(self, timestamps: np.ndarray, target: int) -> int:
        """找到最近的时间戳索引（通用工具）"""
        return int(np.argmin(np.abs(timestamps - target)))

    def _concat_arms(self, left_state: np.ndarray, right_state: np.ndarray) -> np.ndarray:
        """
        拼接左右臂状态

        Args:
            left_state: 左臂状态 (7,)
            right_state: 右臂状态 (7,)

        Returns:
            合并后的状态 (14,)
        """
        return np.concatenate([left_state, right_state], axis=0).astype(np.float32)
