"""Parquet 文件写入器"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict
import numpy as np


class ParquetWriter:
    """LeRobot Parquet 格式写入器"""

    def __init__(self, output_path: str):
        """
        Args:
            output_path: 输出目录路径
        """
        self.output_path = Path(output_path)
        self.data_dir = self.output_path / "data" / "chunk-000"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def write_episode(
        self,
        episode_index: int,
        aligned_frames: List[Dict],
        global_frame_offset: int = 0
    ):
        """
        写入单个 episode 的 Parquet 文件

        Args:
            episode_index: Episode 索引（从 0 开始）
            aligned_frames: 对齐后的帧数据列表
            global_frame_offset: 全局帧索引偏移量
        """
        if not aligned_frames:
            print(f"Warning: Episode {episode_index} has no frames, skipping.")
            return

        # 构造 DataFrame
        rows = []
        for frame_idx, frame in enumerate(aligned_frames):
            row = {
                # Observation
                'observation.state.slave': frame['observation.state.slave'],
                'observation.state.master': frame['observation.state.master'],

                # Images (存储视频路径和时间戳)
                'observation.images.cam_left': self._create_video_frame_ref(
                    'cam_left', episode_index, frame['observation.images.cam_left']
                ),
                'observation.images.cam_right': self._create_video_frame_ref(
                    'cam_right', episode_index, frame['observation.images.cam_right']
                ),
                'observation.images.cam_head': self._create_video_frame_ref(
                    'cam_head', episode_index, frame['observation.images.cam_head']
                ),

                # Action
                'action': frame['action'],

                # Metadata
                'episode_index': episode_index,
                'frame_index': frame_idx,
                'timestamp': frame['timestamp'],
                'index': global_frame_offset + frame_idx,
                'next.done': frame_idx == len(aligned_frames) - 1
            }
            rows.append(row)

        # 转换为 Parquet 兼容格式
        table = self._create_arrow_table(rows)

        # 写入文件
        output_file = self.data_dir / f"episode_{episode_index:06d}.parquet"
        pq.write_table(table, output_file)

        print(f"✓ Wrote episode {episode_index}: {len(rows)} frames → {output_file}")

    def _create_video_frame_ref(self, camera_name: str, episode_index: int, camera_info: Dict) -> Dict:
        """
        创建视频帧引用

        Args:
            camera_name: 相机名称
            episode_index: Episode 索引
            camera_info: 相机信息 {'index': int, 'timestamp': int}

        Returns:
            {'path': str, 'timestamp': float}
        """
        if camera_info is None:
            return {'path': '', 'timestamp': 0.0}

        video_path = f"videos/chunk-000/observation.images.{camera_name}/episode_{episode_index:06d}.mp4"

        # 计算视频时间戳（秒，从 episode 开始）
        # 这里简化处理，使用帧索引 × 帧间隔
        video_timestamp = camera_info['index'] / 25.0  # 假设 25 FPS

        return {
            'path': video_path,
            'timestamp': video_timestamp
        }

    def _create_arrow_table(self, rows: List[Dict]) -> pa.Table:
        """
        创建 Arrow Table

        Args:
            rows: 数据行列表

        Returns:
            Arrow Table
        """
        # 提取各列数据
        data = {
            'observation.state.slave': [row['observation.state.slave'] for row in rows],
            'observation.state.master': [row['observation.state.master'] for row in rows],
            'observation.images.cam_left': [row['observation.images.cam_left'] for row in rows],
            'observation.images.cam_right': [row['observation.images.cam_right'] for row in rows],
            'observation.images.cam_head': [row['observation.images.cam_head'] for row in rows],
            'action': [self._convert_action_to_list(row['action']) for row in rows],
            'episode_index': [row['episode_index'] for row in rows],
            'frame_index': [row['frame_index'] for row in rows],
            'timestamp': [row['timestamp'] for row in rows],
            'index': [row['index'] for row in rows],
            'next.done': [row['next.done'] for row in rows],
        }

        # 创建 schema
        schema = pa.schema([
            ('observation.state.slave', pa.list_(pa.float32(), 14)),
            ('observation.state.master', pa.list_(pa.float32(), 14)),
            ('observation.images.cam_left', pa.struct([
                ('path', pa.string()),
                ('timestamp', pa.float64())
            ])),
            ('observation.images.cam_right', pa.struct([
                ('path', pa.string()),
                ('timestamp', pa.float64())
            ])),
            ('observation.images.cam_head', pa.struct([
                ('path', pa.string()),
                ('timestamp', pa.float64())
            ])),
            ('action', self._get_action_schema(data['action'][0])),
            ('episode_index', pa.int64()),
            ('frame_index', pa.int64()),
            ('timestamp', pa.int64()),
            ('index', pa.int64()),
            ('next.done', pa.bool_()),
        ])

        # 创建 table
        table = pa.table(data, schema=schema)
        return table

    def _convert_action_to_list(self, action):
        """
        将 action 数组转换为 Python list（支持 1D 和 2D）

        Args:
            action: numpy 数组

        Returns:
            Python list or nested list
        """
        if isinstance(action, np.ndarray):
            return action.tolist()
        return action

    def _get_action_schema(self, action_sample):
        """
        根据 action 样本推断 schema

        Args:
            action_sample: action 数据样本 (可能是 list 或 numpy array)

        Returns:
            Arrow 类型
        """
        # 如果是 list，先转换为 numpy 检查维度
        if isinstance(action_sample, list):
            action_sample = np.array(action_sample)

        if action_sample.ndim == 1:
            # 单步 action: (14,)
            return pa.list_(pa.float32(), len(action_sample))
        elif action_sample.ndim == 2:
            # Chunked action: (chunk_size, 14)
            chunk_size, action_dim = action_sample.shape
            return pa.list_(pa.list_(pa.float32(), action_dim), chunk_size)
        else:
            raise ValueError(f"Unexpected action shape: {action_sample.shape}")
