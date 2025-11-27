"""元数据生成器"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


class MetadataGenerator:
    """生成 LeRobot v2.1 元数据文件"""

    def __init__(self, output_path: str, dataset_name: str):
        """
        Args:
            output_path: 输出目录路径
            dataset_name: 数据集名称
        """
        self.output_path = Path(output_path)
        self.dataset_name = dataset_name
        self.meta_dir = self.output_path / "meta"
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def generate_info_json(
        self,
        total_episodes: int,
        total_frames: int,
        action_shape: Tuple,
        camera_names: List[str],
        fps: int = 25
    ):
        """
        生成 meta/info.json

        Args:
            total_episodes: 总 episode 数
            total_frames: 总帧数
            action_shape: action 的 shape
            camera_names: 相机名称列表
            fps: 视频帧率
        """
        # 构造 features schema
        # 双臂关节名称：每臂7个关节 (joint1-6 + gripper)
        joint_names = [
            'left_joint1', 'left_joint2', 'left_joint3',
            'left_joint4', 'left_joint5', 'left_joint6',
            'left_gripper',
            'right_joint1', 'right_joint2', 'right_joint3',
            'right_joint4', 'right_joint5', 'right_joint6',
            'right_gripper'
        ]

        features = {
            'observation.state.slave': {
                'dtype': 'float32',
                'shape': [14],
                'names': joint_names
            },
            'observation.state.master': {
                'dtype': 'float32',
                'shape': [14],
                'names': joint_names
            },
        }

        # 添加相机特征
        for cam_name in camera_names:
            features[f'observation.images.{cam_name}'] = {
                'dtype': 'video',
                'video_info': {
                    'video.fps': fps,
                    'video.codec': 'h264',
                    'video.pix_fmt': 'yuv420p',
                    'video.is_depth_map': False,
                    'has_audio': False
                }
            }

        # 添加 action 特征
        if len(action_shape) == 1:
            # 单步 action: (14,)
            features['action'] = {
                'dtype': 'float32',
                'shape': list(action_shape),
                'names': joint_names
            }
        else:
            # Chunked action: (chunk_size, 14)
            # names 描述两个维度：第一维是时间步，第二维是关节
            features['action'] = {
                'dtype': 'float32',
                'shape': list(action_shape),
                'names': {
                    'dim_0': 'chunk_step',
                    'dim_1': joint_names
                }
            }

        # 添加元数据特征
        features.update({
            'episode_index': {'dtype': 'int64'},
            'frame_index': {'dtype': 'int64'},
            'timestamp': {'dtype': 'int64'},
            'index': {'dtype': 'int64'},
            'next.done': {'dtype': 'bool'}
        })

        # 构造 info.json
        info = {
            'codebase_version': 'v2.1',
            'robot_type': 'airbot_play_dual_arm',
            'total_episodes': total_episodes,
            'total_frames': total_frames,
            'total_tasks': 1,
            'total_videos': total_episodes * len(camera_names),
            'total_chunks': 1,
            'chunks_size': 1000,
            'fps': fps,

            # 路径模板
            'data_path': 'data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet',
            'video_path': 'videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4',

            'features': features,
            'info': {
                'dataset_name': self.dataset_name,
                'cameras': camera_names,
                'alignment_strategy': 'configurable',  # 从配置中获取
                'action_space': 'dual_arm_joint_position'
            }
        }

        # 写入文件
        info_file = self.meta_dir / 'info.json'
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)

        print(f"✓ Generated {info_file}")

    def generate_episodes_jsonl(self, episodes_info: List[Dict]):
        """
        生成 meta/episodes.jsonl

        Args:
            episodes_info: Episodes 信息列表
                [
                    {'episode_index': 0, 'length': 107, 'tasks': [0]},
                    ...
                ]
        """
        episodes_file = self.meta_dir / 'episodes.jsonl'

        with open(episodes_file, 'w') as f:
            for ep_info in episodes_info:
                json.dump(ep_info, f)
                f.write('\n')

        print(f"✓ Generated {episodes_file}")

    def generate_tasks_jsonl(self, task_name: str = "dual_arm_manipulation"):
        """
        生成 meta/tasks.jsonl

        Args:
            task_name: 任务名称
        """
        tasks_file = self.meta_dir / 'tasks.jsonl'

        task = {
            'task_index': 0,
            'task': task_name
        }

        with open(tasks_file, 'w') as f:
            json.dump(task, f)
            f.write('\n')

        print(f"✓ Generated {tasks_file}")

    def generate_all(
        self,
        total_episodes: int,
        total_frames: int,
        action_shape: Tuple,
        camera_names: List[str],
        episodes_info: List[Dict],
        fps: int = 25
    ):
        """
        生成所有元数据文件

        Args:
            total_episodes: 总 episode 数
            total_frames: 总帧数
            action_shape: action 的 shape
            camera_names: 相机名称列表
            episodes_info: Episodes 信息列表
            fps: 视频帧率
        """
        print("\n📝 Generating metadata files...")

        self.generate_info_json(
            total_episodes,
            total_frames,
            action_shape,
            camera_names,
            fps
        )

        self.generate_episodes_jsonl(episodes_info)

        self.generate_tasks_jsonl()

        print("✓ Metadata generation completed!")
