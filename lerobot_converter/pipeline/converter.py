"""主转换器"""

import logging
from pathlib import Path
from typing import Dict, List
import numpy as np
from tqdm import tqdm

from ..utils import io, timestamp, camera
from ..utils.path_utils import detect_episode_format
from ..aligners import NearestAligner, ChunkingAligner, WindowAligner
from ..writers.parquet import ParquetWriter
from ..writers.video import VideoEncoder
from ..writers.metadata import MetadataGenerator
from .config import load_config, get_base_camera_name
from .cleaner import DataCleaner

logger = logging.getLogger(__name__)


class LeRobotConverter:
    """LeRobot v2.1 数据转换器（支持三种对齐策略）"""

    def __init__(self, config_or_path, input_data_path=None, input_images_path=None):
        """
        Args:
            config_or_path: 配置字典或配置文件路径
            input_data_path: 输入关节数据路径（覆盖配置文件）
            input_images_path: 输入图像数据路径（覆盖配置文件）
        """
        # 加载配置
        if isinstance(config_or_path, dict):
            self.config = config_or_path
        else:
            self.config = load_config(config_or_path)

        # 初始化组件
        self.cleaner = DataCleaner(self.config)
        self.aligner = self._create_aligner()
        self.parquet_writer = ParquetWriter(
            self.config['output']['base_path'],
            fps=self.config['video']['fps']
        )
        self.video_encoder = VideoEncoder(
            self.config['output']['base_path'],
            fps=self.config['video']['fps'],
            codec=self.config['video']['codec']
        )
        self.metadata_generator = MetadataGenerator(
            self.config['output']['base_path'],
            self.config['output']['dataset_name']
        )

        # 提取配置（支持路径覆盖）
        self.data_path = Path(input_data_path or self.config['input']['data_path'])
        self.images_path = Path(input_images_path or self.config['input']['images_path'])
        self.arms = self.config['robot']['arms']
        self.cameras = self.config['cameras']
        self.base_camera_name = get_base_camera_name(self.config)

        logger.info("="*60)
        logger.info("LeRobot v2.1 Converter")
        logger.info("="*60)
        logger.info(f"Strategy: {self.config['alignment']['strategy']}")
        logger.info(f"Base camera: {self.base_camera_name}")
        logger.info(f"Output: {self.config['output']['base_path']}")
        logger.info("="*60)

    def _create_aligner(self):
        """工厂方法：根据配置创建对齐器"""
        strategy = self.config['alignment']['strategy']

        if strategy == 'nearest':
            return NearestAligner(self.config['alignment'])
        elif strategy == 'chunking':
            return ChunkingAligner(self.config['alignment'])
        elif strategy == 'window':
            return WindowAligner(self.config['alignment'])
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def convert(self, episode_id: str = None):
        """
        执行转换

        Args:
            episode_id: 如果指定，只转换单个 episode；否则转换所有
        """
        if episode_id:
            # 单 episode 转换
            logger.info(f"Converting single episode: {episode_id}")
            valid_episodes = [episode_id]
        else:
            # 批量转换
            valid_episodes = self.cleaner.scan_and_filter()

        if not valid_episodes:
            logger.warning("No valid episodes found!")
            return

        # 转换所有 episodes
        all_episodes_info = []
        global_frame_offset = 0
        failed_episodes = []

        logger.info(f"Converting {len(valid_episodes)} episodes...")

        for ep_idx, ep_id in enumerate(tqdm(valid_episodes, desc="Converting")):
            try:
                episode_info = self._convert_episode(ep_id, ep_idx, global_frame_offset)
                all_episodes_info.append(episode_info)
                global_frame_offset += episode_info['length']
            except Exception as e:
                logger.error(f"Failed to convert episode {ep_id}: {e}")
                failed_episodes.append(ep_id)
                continue  # 继续处理其他 episodes

        if failed_episodes:
            logger.warning(f"Failed to convert {len(failed_episodes)} episodes: {failed_episodes}")

        if not all_episodes_info:
            logger.error("All episodes failed to convert!")
            return

        # 生成元数据
        total_frames = sum(ep['length'] for ep in all_episodes_info)
        camera_names = [cam['name'] for cam in self.cameras]

        self.metadata_generator.generate_all(
            total_episodes=len(valid_episodes),
            total_frames=total_frames,
            action_shape=self.aligner.get_action_shape(),
            camera_names=camera_names,
            episodes_info=all_episodes_info,
            fps=self.config['video']['fps']
        )

        logger.info("="*60)
        logger.info("✓ Conversion completed!")
        logger.info(f"  Episodes: {len(valid_episodes)}")
        logger.info(f"  Total frames: {total_frames}")
        logger.info(f"  Output: {self.config['output']['base_path']}")
        logger.info("="*60)

    def _convert_episode(self, episode_id: str, episode_index: int, global_frame_offset: int) -> Dict:
        """
        转换单个 episode

        Args:
            episode_id: Episode ID
            episode_index: Episode 索引
            global_frame_offset: 全局帧索引偏移

        Returns:
            Episode 信息字典
        """
        # 1. 加载四臂关节数据
        arm_data = self._load_arm_data(episode_id)

        # 2. 加载相机元数据和同步相机
        camera_data = self._load_camera_data(episode_id)
        base_camera_timestamps = camera_data[self.base_camera_name]['timestamps']

        # 同步所有相机到基准相机
        synced_camera_frames = camera.sync_cameras(
            base_camera_timestamps,
            camera_data,
            tolerance_ms=self.config['alignment']['tolerance_ms']
        )

        # 3. 时间对齐（应用策略）
        aligned_frames = self.aligner.align(
            base_camera_timestamps,
            arm_data,
            synced_camera_frames
        )

        # 4. 写入 Parquet
        self.parquet_writer.write_episode(
            episode_index,
            aligned_frames,
            global_frame_offset
        )

        # 5. 编码视频
        camera_images = self._get_camera_images(episode_id, synced_camera_frames)
        camera_names = [cam['name'] for cam in self.cameras]

        self.video_encoder.encode_episode(
            episode_index,
            camera_images,
            camera_names
        )

        # 返回 episode 信息
        return {
            'episode_index': episode_index,
            'length': len(aligned_frames),
            'tasks': [0]
        }

    def _load_arm_data(self, episode_id: str) -> Dict:
        """
        加载四臂关节数据（自动适配新旧格式）

        Returns:
            {
                'left_slave': {'timestamps': array, 'states': array},
                'left_master': {...},
                'right_slave': {...},
                'right_master': {...}
            }
        """
        arm_data = {}

        # 使用工具函数检测格式并获取数据目录
        ep_base_dir = self.data_path / episode_id
        _, ep_data_dir, _ = detect_episode_format(ep_base_dir, self.images_path)

        for arm in self.arms:
            arm_file = ep_data_dir / arm['file']
            timestamps, states = io.load_joint_data(
                str(arm_file),
                joints_dim=self.config['robot']['joints_per_arm']
            )

            arm_data[arm['name']] = {
                'timestamps': timestamps,
                'states': states
            }

        return arm_data

    def _load_camera_data(self, episode_id: str) -> Dict:
        """
        加载相机数据（自动适配新旧格式）

        Returns:
            {
                'cam_left': {'timestamps': array, 'images': [...]},
                'cam_right': {...},
                'cam_head': {...}
            }
        """
        # 使用工具函数检测格式并获取图像目录
        ep_base_dir = self.data_path / episode_id
        _, _, ep_images_dir = detect_episode_format(ep_base_dir, self.images_path)

        metadata_file = ep_images_dir / 'metadata.json'
        metadata = io.load_json(str(metadata_file))

        camera_data = {}

        for cam in self.cameras:
            cam_name = cam['name']
            cam_meta = metadata['cameras'].get(cam_name, {})

            camera_data[cam_name] = {
                'timestamps': np.array(cam_meta['timestamps'], dtype=np.int64),
                'frame_count': cam_meta['frame_count']
            }

        return camera_data

    def _get_camera_images(self, episode_id: str, synced_frames: List[Dict]) -> Dict:
        """
        获取相机图像路径列表（自动适配新旧格式）

        Returns:
            {
                'cam_left': ['/path/to/img1.jpg', ...],
                'cam_right': [...],
                'cam_head': [...]
            }
        """
        # 使用工具函数检测格式并获取图像目录
        ep_base_dir = self.data_path / episode_id
        _, _, ep_images_dir = detect_episode_format(ep_base_dir, self.images_path)

        camera_images = {}
        missing_count = 0  # 统计缺失的图像数量

        for cam in self.cameras:
            cam_name = cam['name']
            cam_dir = ep_images_dir / cam_name

            # 获取该相机对应的图像索引
            images = []
            for frame in synced_frames:
                if cam_name in frame:
                    cam_info = frame[cam_name]
                    # 获取该索引对应的图像文件
                    # 注意：图像文件以时间戳命名
                    img_ts = cam_info['timestamp']
                    img_file = cam_dir / f"{img_ts}.jpg"

                    if img_file.exists():
                        images.append(str(img_file))
                    else:
                        # 图像文件缺失，记录警告
                        logger.warning(f"Missing image file: {img_file}")
                        missing_count += 1

            camera_images[cam_name] = images

        # 报告缺失图像的总数
        if missing_count > 0:
            logger.warning(f"Total missing images for episode {episode_id}: {missing_count}")

        return camera_images
