"""视频编码器"""

import cv2
from pathlib import Path
from typing import List
from tqdm import tqdm


class VideoEncoder:
    """将图像序列编码为 MP4 视频"""

    def __init__(self, output_path: str, fps: int = 25, codec: str = 'h264',
                 crf: int = 23, preset: str = 'medium'):
        """
        Args:
            output_path: 输出目录路径
            fps: 视频帧率
            codec: 编码器
            crf: 质量参数 (0-51, 越小质量越高)
            preset: 编码速度预设
        """
        self.output_path = Path(output_path)
        self.fps = fps
        self.codec = codec
        self.crf = crf
        self.preset = preset

        self.videos_dir = self.output_path / "videos" / "chunk-000"

    def encode_episode(
        self,
        episode_index: int,
        camera_images: dict,
        camera_names: List[str]
    ):
        """
        为一个 episode 编码所有相机的视频

        Args:
            episode_index: Episode 索引
            camera_images: 相机图像路径字典
                {
                    'cam_left': ['/path/to/img1.jpg', '/path/to/img2.jpg', ...],
                    'cam_right': [...],
                    'cam_head': [...]
                }
            camera_names: 相机名称列表
        """
        for cam_name in camera_names:
            if cam_name not in camera_images:
                print(f"Warning: Camera {cam_name} not found in episode {episode_index}")
                continue

            self._encode_camera(
                episode_index,
                cam_name,
                camera_images[cam_name]
            )

    def _encode_camera(
        self,
        episode_index: int,
        camera_name: str,
        image_paths: List[str]
    ):
        """
        为单个相机编码视频

        Args:
            episode_index: Episode 索引
            camera_name: 相机名称
            image_paths: 图像文件路径列表
        """
        if not image_paths:
            print(f"Warning: No images for {camera_name} in episode {episode_index}")
            return

        # 创建输出目录
        camera_video_dir = self.videos_dir / f"observation.images.{camera_name}"
        camera_video_dir.mkdir(parents=True, exist_ok=True)

        output_file = camera_video_dir / f"episode_{episode_index:06d}.mp4"

        # 读取第一张图片获取尺寸
        first_img = cv2.imread(image_paths[0])
        if first_img is None:
            print(f"Error: Cannot read image {image_paths[0]}")
            return

        height, width = first_img.shape[:2]

        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 或 'avc1' for h264
        video_writer = cv2.VideoWriter(
            str(output_file),
            fourcc,
            self.fps,
            (width, height)
        )

        # 写入所有帧
        for img_path in image_paths:
            frame = cv2.imread(img_path)
            if frame is None:
                print(f"Warning: Cannot read image {img_path}, skipping")
                continue
            video_writer.write(frame)

        video_writer.release()

        print(f"  ✓ Encoded {camera_name}: {len(image_paths)} frames → {output_file}")

    def encode_all_cameras(
        self,
        episodes_data: List[dict],
        camera_names: List[str]
    ):
        """
        批量编码所有 episodes 的所有相机

        Args:
            episodes_data: Episodes 数据列表
                [
                    {
                        'episode_index': 0,
                        'camera_images': {
                            'cam_left': [...],
                            'cam_right': [...],
                            'cam_head': [...]
                        }
                    },
                    ...
                ]
            camera_names: 相机名称列表
        """
        print(f"\n📹 Encoding videos for {len(episodes_data)} episodes...")

        for ep_data in tqdm(episodes_data, desc="Encoding videos"):
            self.encode_episode(
                ep_data['episode_index'],
                ep_data['camera_images'],
                camera_names
            )

        print(f"✓ Video encoding completed!")
