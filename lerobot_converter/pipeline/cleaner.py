"""数据清洗和过滤"""

import logging
from pathlib import Path
from typing import List, Dict
import json

from ..utils.path_utils import detect_episode_format

logger = logging.getLogger(__name__)


class DataCleaner:
    """数据清洗和 Episode 过滤"""

    def __init__(self, config: Dict):
        """
        Args:
            config: 配置字典
        """
        self.config = config
        self.data_path = Path(config['input']['data_path'])
        self.images_path = Path(config['input']['images_path'])

        self.min_duration = config['filtering'].get('min_duration_sec', 0.5)
        self.require_all_cameras = config['filtering'].get('require_all_cameras', True)

    def scan_and_filter(self) -> List[str]:
        """
        扫描并过滤有效的 episodes

        Returns:
            有效的 episode ID 列表
        """
        logger.info("Scanning episodes...")

        # 扫描所有 episodes
        all_episodes = self._scan_episodes()

        logger.info(f"Found {len(all_episodes)} episodes")

        # 过滤
        valid_episodes = []
        filtered_out = []

        for ep_id in all_episodes:
            is_valid, reason = self._validate_episode(ep_id)

            if is_valid:
                valid_episodes.append(ep_id)
            else:
                filtered_out.append((ep_id, reason))

        # 打印结果
        logger.info(f"Valid episodes: {len(valid_episodes)}")

        if filtered_out:
            logger.info(f"Filtered out: {len(filtered_out)}")
            for ep_id, reason in filtered_out:
                logger.debug(f"  - {ep_id}: {reason}")

        return sorted(valid_episodes)

    def _scan_episodes(self) -> List[str]:
        """扫描所有 episode 目录"""
        episodes = []

        for ep_dir in self.data_path.iterdir():
            if ep_dir.is_dir() and ep_dir.name.startswith('episode_'):
                episodes.append(ep_dir.name)

        return sorted(episodes)

    def _validate_episode(self, episode_id: str) -> tuple:
        """
        验证单个 episode（自动适配新旧格式）

        Args:
            episode_id: Episode ID

        Returns:
            (is_valid, reason)
        """
        ep_base_dir = self.data_path / episode_id

        # 使用工具函数检测格式并获取路径
        _, ep_data_dir, ep_images_dir = detect_episode_format(ep_base_dir, self.images_path)

        # 1. 检查图像目录是否存在
        if not ep_images_dir.exists():
            return False, "Missing images directory"

        # 2. 检查关节数据文件
        arms = self.config['robot']['arms']
        for arm in arms:
            arm_file = ep_data_dir / arm['file']
            if not arm_file.exists():
                return False, f"Missing {arm['file']}"

        # 3. 检查元数据 (优先在 joints 目录下查找，因为它包含更完整的信息)
        metadata_file = ep_data_dir / 'metadata.json'
        if not metadata_file.exists():
            # 回退到 images 目录
            metadata_file = ep_images_dir / 'metadata.json'
            if not metadata_file.exists():
                return False, "Missing metadata.json"

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # 4. 检查时长
        duration = metadata.get('duration_sec', 0)
        if duration < self.min_duration:
            return False, f"Duration too short: {duration:.2f}s < {self.min_duration}s"

        # 5. 检查相机数据
        if self.require_all_cameras:
            camera_names = [cam['name'] for cam in self.config['cameras']]
            for cam_name in camera_names:
                cam_dir = ep_images_dir / cam_name
                if not cam_dir.exists():
                    return False, f"Missing camera {cam_name}"

                # 检查是否有图像
                images = list(cam_dir.glob('*.jpg'))
                if len(images) == 0:
                    return False, f"No images in camera {cam_name}"

        return True, "OK"

    def get_episode_stats(self, episode_id: str) -> Dict:
        """
        获取 episode 统计信息（自动适配新旧格式）

        Args:
            episode_id: Episode ID

        Returns:
            统计信息字典
        """
        ep_base_dir = self.data_path / episode_id

        # 使用工具函数检测格式并获取路径
        _, ep_data_dir, ep_images_dir = detect_episode_format(ep_base_dir, self.images_path)

        # 读取元数据（优先在 joints 目录，因为它包含更完整的信息）
        metadata_file = ep_data_dir / 'metadata.json'
        if not metadata_file.exists():
            metadata_file = ep_images_dir / 'metadata.json'

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # 统计相机帧数
        camera_frame_counts = {}
        for cam in self.config['cameras']:
            cam_name = cam['name']
            cam_dir = ep_images_dir / cam_name
            if cam_dir.exists():
                images = list(cam_dir.glob('*.jpg'))
                camera_frame_counts[cam_name] = len(images)

        return {
            'episode_id': episode_id,
            'duration_sec': metadata.get('duration_sec', 0),
            'camera_frames': camera_frame_counts,
            'arm_frames': {
                arm_name: arm_data['total_frames']
                for arm_name, arm_data in metadata.get('arms', {}).items()
            }
        }
