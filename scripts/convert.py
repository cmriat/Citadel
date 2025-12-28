"""
Script to convert HDF5 data to LeRobot dataset v2.1 format.

Usage:
    pixi run python test/lerobot_convert_v21.py \
        --hdf5-path /home/admin01/maoz/limx/assetes/episode_01_2025-12-19-16-13-07.hdf5 \
        --output-dir /home/admin01/maoz/limx/assetes/episode_0001 \
        --robot-type "limx Tron2" \
        --fps 30 \
        --task "Fold the laundry"
"""

import json
from pathlib import Path
from typing import Dict
import h5py
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import av
import tyro


def decode_jpeg_frames(hdf5_file, camera_name: str) -> np.ndarray:
    """解码JPEG压缩的图像帧

    Args:
        hdf5_file: HDF5文件对象
        camera_name: 相机名称 (cam_env, cam_left_wrist, cam_right_wrist)

    Returns:
        np.ndarray: [N, H, W, 3] RGB uint8图像数组
    """
    from PIL import Image
    import io

    jpeg_frames = hdf5_file[f"images/{camera_name}/frames_jpeg"][:]
    decoded_frames = []

    for jpeg_bytes in jpeg_frames:
        # PIL解码JPEG
        image = Image.open(io.BytesIO(jpeg_bytes))
        # 确保RGB格式
        if image.mode != 'RGB':
            image = image.convert('RGB')
        # 转为numpy数组
        image_array = np.array(image, dtype=np.uint8)
        decoded_frames.append(image_array)

    return np.stack(decoded_frames, axis=0)


def reconstruct_joint_vector(hdf5_group, num_joints=6) -> np.ndarray:
    """从分散的joint{1-6}_pos重构为向量

    Args:
        hdf5_group: HDF5组对象 (例如 f["joints/left_slave"])
        num_joints: 关节数量，默认6

    Returns:
        np.ndarray: [N, num_joints] 关节位置数组
    """
    joints = []
    for i in range(1, num_joints + 1):
        joint_key = f"joint{i}_pos"
        joints.append(hdf5_group[joint_key][:])
    return np.column_stack(joints)


def align_data_to_reference(ref_timestamps, data, data_timestamps, data_name):
    """通用的时间对齐函数 (最近邻)

    Args:
        ref_timestamps: [N_ref] 参考时间戳
        data: [N_data, ...] 待对齐数据 (可以是图像或关节)
        data_timestamps: [N_data] 数据时间戳
        data_name: 数据名称 (用于日志)

    Returns:
        aligned_data: [N_ref, ...] 对齐后的数据
    """
    aligned_indices = []

    for ref_ts in ref_timestamps:
        closest_idx = np.argmin(np.abs(data_timestamps - ref_ts))
        aligned_indices.append(closest_idx)

    aligned_data = data[aligned_indices]

    # 计算对齐质量
    time_errors = np.abs(data_timestamps[aligned_indices] - ref_timestamps)
    print(f"  {data_name}: 平均误差={np.mean(time_errors)/1e6:.2f}ms, 最大误差={np.max(time_errors)/1e6:.2f}ms")

    return aligned_data


def load_episode_v1_format(ep_path: Path) -> Dict:
    """加载online_test_hdf5_v1格式的Episode数据

    数据格式:
        images/cam_env/frames_jpeg - JPEG压缩图像
        joints/{left|right}_{master|slave}/joint{1-6}_pos
        joints/{left|right}_{master|slave}/eef_gripper_joint_pos

    Returns:
        {
            'images_env': [N, H, W, 3] uint8,
            'images_left_wrist': [N, H, W, 3] uint8,
            'images_right_wrist': [N, H, W, 3] uint8,
            'state': [N, 16] float32,
            'action': [N, 16] float32
        }
    """
    with h5py.File(ep_path, "r") as f:
        # ========== 1. 确定参考基准时间戳 (最少帧数相机) ==========
        cameras_info = {
            'cam_env': f["images/cam_env/timestamps"][:],
            'cam_left_wrist': f["images/cam_left_wrist/timestamps"][:],
            'cam_right_wrist': f["images/cam_right_wrist/timestamps"][:]
        }

        # 找到帧数最少的相机作为基准
        min_camera = min(cameras_info, key=lambda k: len(cameras_info[k]))
        reference_timestamps = cameras_info[min_camera]
        N_frames = len(reference_timestamps)

        print(f"\n⏱️  时间对齐基准: {min_camera} ({N_frames}帧)")

        # ========== 2. 解码并对齐图像 ==========
        print("\n📸 图像对齐:")

        # cam_env
        images_env_raw = decode_jpeg_frames(f, "cam_env")
        if min_camera != 'cam_env':
            images_env = align_data_to_reference(
                reference_timestamps,
                images_env_raw,
                cameras_info['cam_env'],
                'cam_env'
            )
        else:
            images_env = images_env_raw
            print(f"  cam_env: 无需对齐 (基准相机)")

        # cam_left_wrist
        images_left_raw = decode_jpeg_frames(f, "cam_left_wrist")
        if min_camera != 'cam_left_wrist':
            images_left = align_data_to_reference(
                reference_timestamps,
                images_left_raw,
                cameras_info['cam_left_wrist'],
                'cam_left_wrist'
            )
        else:
            images_left = images_left_raw
            print(f"  cam_left_wrist: 无需对齐 (基准相机)")

        # cam_right_wrist
        images_right_raw = decode_jpeg_frames(f, "cam_right_wrist")
        if min_camera != 'cam_right_wrist':
            images_right = align_data_to_reference(
                reference_timestamps,
                images_right_raw,
                cameras_info['cam_right_wrist'],
                'cam_right_wrist'
            )
        else:
            images_right = images_right_raw
            print(f"  cam_right_wrist: 无需对齐 (基准相机)")

        # ========== 3. 读取关节数据 (slave) ==========
        print("\n🦾 关节对齐:")

        # 3.1 读取left slave数据
        left_joints_raw = reconstruct_joint_vector(f["joints/left_slave"], 6)
        left_gripper_raw = f["joints/left_slave/eef_gripper_joint_pos"][:][:, np.newaxis]

        # 3.2 读取left slave时间戳
        left_joint_sec = f["joints/left_slave/timestamp_sec"][:]
        left_joint_nsec = f["joints/left_slave/timestamp_nanosec"][:]
        left_joint_timestamps = left_joint_sec * 1e9 + left_joint_nsec

        # 3.3 读取right slave数据
        right_joints_raw = reconstruct_joint_vector(f["joints/right_slave"], 6)
        right_gripper_raw = f["joints/right_slave/eef_gripper_joint_pos"][:][:, np.newaxis]

        # 3.4 读取right slave时间戳
        right_joint_sec = f["joints/right_slave/timestamp_sec"][:]
        right_joint_nsec = f["joints/right_slave/timestamp_nanosec"][:]
        right_joint_timestamps = right_joint_sec * 1e9 + right_joint_nsec

        # 3.5 对齐关节数据到基准时间戳（各自使用自己的时间戳）
        left_joints = align_data_to_reference(reference_timestamps, left_joints_raw, left_joint_timestamps, 'left_joints')
        left_gripper = align_data_to_reference(reference_timestamps, left_gripper_raw, left_joint_timestamps, 'left_gripper')
        right_joints = align_data_to_reference(reference_timestamps, right_joints_raw, right_joint_timestamps, 'right_joints')
        right_gripper = align_data_to_reference(reference_timestamps, right_gripper_raw, right_joint_timestamps, 'right_gripper')

        # ========== 4. 组装State (16维) ==========
        state = np.concatenate([
            left_joints,   # [N, 6]
            left_gripper,  # [N, 1]
            right_joints,  # [N, 6]
            right_gripper  # [N, 1]
        ], axis=1).astype(np.float32)  # [N, 16]

        # ========== 5. 组装Action (16维) ==========
        if "left_master" in f["joints"]:
            print("\n🎮 动作对齐:")

            # 读取left master数据
            left_joints_cmd_raw = reconstruct_joint_vector(f["joints/left_master"], 6)
            left_gripper_cmd_raw = f["joints/left_master/eef_gripper_joint_pos"][:][:, np.newaxis]

            # 读取left master时间戳
            left_cmd_sec = f["joints/left_master/timestamp_sec"][:]
            left_cmd_nsec = f["joints/left_master/timestamp_nanosec"][:]
            left_cmd_timestamps = left_cmd_sec * 1e9 + left_cmd_nsec

            # 读取right master数据
            right_joints_cmd_raw = reconstruct_joint_vector(f["joints/right_master"], 6)
            right_gripper_cmd_raw = f["joints/right_master/eef_gripper_joint_pos"][:][:, np.newaxis]

            # 读取right master时间戳
            right_cmd_sec = f["joints/right_master/timestamp_sec"][:]
            right_cmd_nsec = f["joints/right_master/timestamp_nanosec"][:]
            right_cmd_timestamps = right_cmd_sec * 1e9 + right_cmd_nsec

            # 对齐到基准时间戳
            left_joints_cmd = align_data_to_reference(reference_timestamps, left_joints_cmd_raw, left_cmd_timestamps, 'left_joints_cmd')
            left_gripper_cmd = align_data_to_reference(reference_timestamps, left_gripper_cmd_raw, left_cmd_timestamps, 'left_gripper_cmd')
            right_joints_cmd = align_data_to_reference(reference_timestamps, right_joints_cmd_raw, right_cmd_timestamps, 'right_joints_cmd')
            right_gripper_cmd = align_data_to_reference(reference_timestamps, right_gripper_cmd_raw, right_cmd_timestamps, 'right_gripper_cmd')

            action = np.concatenate([
                left_joints_cmd,
                left_gripper_cmd,
                right_joints_cmd,
                right_gripper_cmd
            ], axis=1).astype(np.float32)

            print("\n✅ 使用master数据作为action")
        else:
            action = state.copy()
            print("\n⚠️  警告: master数据不存在，复制slave作为action")

        # ========== 6. 返回对齐后的数据 ==========
        print(f"\n✅ 数据加载完成: {N_frames}帧\n")

        return {
            'images_env': images_env,
            'images_left_wrist': images_left,
            'images_right_wrist': images_right,
            'state': state,
            'action': action
        }


def encode_video_frames(frames: np.ndarray, output_path: Path, fps: int = 30):
    """Encode RGB frame sequence to MP4 video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    container = av.open(str(output_path), mode='w')
    stream = container.add_stream('h264', rate=fps)
    stream.width = frames.shape[2]   # 640
    stream.height = frames.shape[1]  # 480
    stream.pix_fmt = 'yuv420p'
    stream.options = {'crf': '23'}

    for frame in frames:
        av_frame = av.VideoFrame.from_ndarray(frame, format='rgb24')
        for packet in stream.encode(av_frame):
            container.mux(packet)

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    container.close()


def create_episode_parquet(
    episode_data: Dict,
    output_path: Path,
    episode_index: int = 0,
    fps: int = 30
):
    """Create Parquet file for a single episode."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    num_frames = len(episode_data['state'])

    # Create timestamp as float32 (seconds)
    timestamps = (np.arange(num_frames) / float(fps)).astype(np.float32).tolist()

    table = pa.table({
        'observation.state': episode_data['state'].tolist(),
        'action': episode_data['action'].tolist(),
        'timestamp': timestamps,
        'frame_index': np.arange(num_frames).tolist(),
        'episode_index': [episode_index] * num_frames,
        'index': np.arange(num_frames).tolist(),
        'task_index': [0] * num_frames,
    })

    pq.write_table(table, output_path)


def create_output_structure(output_dir: Path):
    """Create LeRobot v2.1 directory structure."""
    (output_dir / "meta").mkdir(parents=True, exist_ok=True)
    (output_dir / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)

    for video_key in ["observation.images.cam_env",
                      "observation.images.cam_left_wrist",
                      "observation.images.cam_right_wrist"]:
        (output_dir / "videos" / "chunk-000" / video_key).mkdir(parents=True, exist_ok=True)


def generate_info_json(
    output_dir: Path,
    total_frames: int,
    fps: int,
    robot_type: str,
    dataset_name: str
):
    """Generate info.json metadata file in meta/ directory."""
    info = {
        "codebase_version": "v2.1",
        "robot_type": robot_type,
        "total_episodes": 1,
        "total_frames": total_frames,
        "total_tasks": 1,
        "total_videos": 3,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": fps,
        "splits": {
            "train": "0:1"
        },
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {
            "observation.state": {
                "dtype": "float32",
                "shape": [14],
                "names": [
                    "left_joint1", "left_joint2", "left_joint3",
                    "left_joint4", "left_joint5", "left_joint6",
                    "left_gripper",
                    "right_joint1", "right_joint2", "right_joint3",
                    "right_joint4", "right_joint5", "right_joint6",
                    "right_gripper"
                ]
            },
            "action": {
                "dtype": "float32",
                "shape": [14],
                "names": [
                    "left_joint1", "left_joint2", "left_joint3",
                    "left_joint4", "left_joint5", "left_joint6",
                    "left_gripper",
                    "right_joint1", "right_joint2", "right_joint3",
                    "right_joint4", "right_joint5", "right_joint6",
                    "right_gripper"
                ]
            },
            "observation.images.cam_env": {
                "dtype": "video",
                "shape": [480, 640, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": 480,
                    "video.width": 640,
                    "video.codec": "libx264",
                    "video.pix_fmt": "rgb24",
                    "video.is_depth_map": False,
                    "video.fps": fps,
                    "video.channels": 3,
                    "has_audio": False
                }
            },
            "observation.images.cam_left_wrist": {
                "dtype": "video",
                "shape": [480, 640, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": 480,
                    "video.width": 640,
                    "video.codec": "libx264",
                    "video.pix_fmt": "rgb24",
                    "video.is_depth_map": False,
                    "video.fps": fps,
                    "video.channels": 3,
                    "has_audio": False
                }
            },
            "observation.images.cam_right_wrist": {
                "dtype": "video",
                "shape": [480, 640, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": 480,
                    "video.width": 640,
                    "video.codec": "libx264",
                    "video.pix_fmt": "rgb24",
                    "video.is_depth_map": False,
                    "video.fps": fps,
                    "video.channels": 3,
                    "has_audio": False
                }
            },
            "timestamp": {
                "dtype": "float32",
                "shape": [1],
                "names": None
            },
            "frame_index": {
                "dtype": "int64",
                "shape": [1],
                "names": None
            },
            "episode_index": {
                "dtype": "int64",
                "shape": [1],
                "names": None
            },
            "index": {
                "dtype": "int64",
                "shape": [1],
                "names": None
            },
            "task_index": {
                "dtype": "int64",
                "shape": [1],
                "names": None
            }
        },
        "info": {
            "dataset_name": dataset_name,
            "cameras": ["cam_left_wrist", "cam_right_wrist", "cam_env"],
            "alignment_strategy": "configurable",
            "action_space": "dual_arm_joint_position"
        }
    }

    with open(output_dir / "meta" / "info.json", "w") as f:
        json.dump(info, f, indent=2)


def generate_tasks_jsonl(output_dir: Path, task: str):
    """Generate tasks.jsonl metadata file in meta/ directory."""
    with open(output_dir / "meta" / "tasks.jsonl", "w") as f:
        f.write(json.dumps({"task_index": 0, "task": task}) + "\n")


def generate_episodes_jsonl(output_dir: Path, num_frames: int, task: str):
    """Generate episodes.jsonl metadata file in meta/ directory."""
    with open(output_dir / "meta" / "episodes.jsonl", "w") as f:
        f.write(json.dumps({
            "episode_index": 0,
            "tasks": [task],  # Task names as strings, not indices
            "length": num_frames
        }) + "\n")


def compute_episode_stats(episode_data: Dict, episode_index: int, fps: int) -> Dict:
    """Compute statistics for a single episode."""
    state = episode_data['state']
    action = episode_data['action']
    num_frames = len(state)

    # Compute timestamps in seconds
    timestamps = np.arange(num_frames) / float(fps)

    stats = {
        "episode_index": episode_index,
        "stats": {
            "observation.state": {
                "min": state.min(axis=0).tolist(),
                "max": state.max(axis=0).tolist(),
                "mean": state.mean(axis=0).tolist(),
                "std": state.std(axis=0).tolist(),
                "count": [num_frames]
            },
            "action": {
                "min": action.min(axis=0).tolist(),
                "max": action.max(axis=0).tolist(),
                "mean": action.mean(axis=0).tolist(),
                "std": action.std(axis=0).tolist(),
                "count": [num_frames]
            },
        }
    }

    # Compute image statistics (normalize to [0, 1])
    for cam_key in ['cam_env', 'cam_left_wrist', 'cam_right_wrist']:
        images_key = f"images_{cam_key.replace('cam_', '')}"
        images = episode_data[images_key].astype(np.float32) / 255.0

        # Sample 100 frames for image statistics (to reduce computation)
        num_samples = min(100, num_frames)
        sample_indices = np.linspace(0, num_frames - 1, num_samples, dtype=int)
        images_sampled = images[sample_indices]

        # Compute per-channel statistics
        min_vals = images_sampled.min(axis=(0, 1, 2))  # [C]
        max_vals = images_sampled.max(axis=(0, 1, 2))  # [C]
        mean_vals = images_sampled.mean(axis=(0, 1, 2))  # [C]
        std_vals = images_sampled.std(axis=(0, 1, 2))  # [C]

        stats["stats"][f"observation.images.{cam_key}"] = {
            "min": [[[float(v)]] for v in min_vals],
            "max": [[[float(v)]] for v in max_vals],
            "mean": [[[float(v)]] for v in mean_vals],
            "std": [[[float(v)]] for v in std_vals],
            "count": [num_samples]
        }

    # Compute timestamp statistics
    stats["stats"]["timestamp"] = {
        "min": [float(timestamps.min())],
        "max": [float(timestamps.max())],
        "mean": [float(timestamps.mean())],
        "std": [float(timestamps.std())],
        "count": [num_frames]
    }

    # Compute frame_index statistics
    frame_indices = np.arange(num_frames)
    stats["stats"]["frame_index"] = {
        "min": [int(frame_indices.min())],
        "max": [int(frame_indices.max())],
        "mean": [float(frame_indices.mean())],
        "std": [float(frame_indices.std())],
        "count": [num_frames]
    }

    # Compute episode_index statistics (all same value)
    stats["stats"]["episode_index"] = {
        "min": [episode_index],
        "max": [episode_index],
        "mean": [float(episode_index)],
        "std": [0.0],
        "count": [num_frames]
    }

    # Compute index statistics
    stats["stats"]["index"] = {
        "min": [int(frame_indices.min())],
        "max": [int(frame_indices.max())],
        "mean": [float(frame_indices.mean())],
        "std": [float(frame_indices.std())],
        "count": [num_frames]
    }

    # Compute task_index statistics (all 0 for single task)
    stats["stats"]["task_index"] = {
        "min": [0],
        "max": [0],
        "mean": [0.0],
        "std": [0.0],
        "count": [num_frames]
    }

    return stats


def generate_episodes_stats_jsonl(output_dir: Path, stats_list: list):
    """Generate episodes_stats.jsonl metadata file in meta/ directory."""
    with open(output_dir / "meta" / "episodes_stats.jsonl", "w") as f:
        for stats in stats_list:
            f.write(json.dumps(stats) + "\n")


def convert_hdf5_to_lerobot_v21(
    hdf5_path: Path,
    output_dir: Path,
    robot_type: str = "limx Tron2",
    fps: int = 30,
    task: str = "Fold the laundry"
):
    """Convert HDF5 episode to LeRobot v2.1 format."""
    dataset_name = output_dir.name
    print(f"Converting {hdf5_path} to LeRobot v2.1 format...")
    print(f"Output directory: {output_dir}")
    print(f"Dataset name: {dataset_name}")

    # 1. Create output directory structure
    create_output_structure(output_dir)

    # 2. Load HDF5 data
    print("\nLoading HDF5 data...")
    episode_data = load_episode_v1_format(hdf5_path)
    num_frames = len(episode_data['state'])
    print(f"Loaded {num_frames} frames")
    print(f"  State shape: {episode_data['state'].shape}")
    print(f"  Action shape: {episode_data['action'].shape}")

    # 3. Encode videos
    print("\nEncoding videos...")
    for cam_key in ['cam_env', 'cam_left_wrist', 'cam_right_wrist']:
        video_path = output_dir / "videos" / "chunk-000" / \
                     f"observation.images.{cam_key}" / "episode_000000.mp4"

        images_key = f"images_{cam_key.replace('cam_', '')}"
        print(f"  Encoding {cam_key}... ", end="", flush=True)
        encode_video_frames(episode_data[images_key], video_path, fps)
        print(f"✓ {video_path.stat().st_size / 1024 / 1024:.1f} MB")

    # 4. Generate Parquet data file
    print("\nGenerating Parquet data file...")
    parquet_path = output_dir / "data" / "chunk-000" / "episode_000000.parquet"
    create_episode_parquet(episode_data, parquet_path, episode_index=0, fps=fps)
    print(f"  ✓ {parquet_path}")

    # 5. Generate metadata files in meta/ directory
    print("\nGenerating metadata files...")
    generate_info_json(output_dir, num_frames, fps, robot_type, dataset_name)
    print("  ✓ meta/info.json")

    generate_tasks_jsonl(output_dir, task)
    print("  ✓ meta/tasks.jsonl")

    generate_episodes_jsonl(output_dir, num_frames, task)
    print("  ✓ meta/episodes.jsonl")

    # 6. Compute and generate episode statistics
    print("\nComputing episode statistics...")
    stats = compute_episode_stats(episode_data, episode_index=0, fps=fps)
    generate_episodes_stats_jsonl(output_dir, [stats])
    print("  ✓ meta/episodes_stats.jsonl")

    print(f"\n✅ Conversion complete!")
    print(f"   Episode location: {output_dir}")
    print(f"   Frames: {num_frames}")
    print(f"   Videos: 3")
    print(f"\nDirectory structure:")
    print(f"  {output_dir.name}/")
    print(f"  ├── meta/")
    print(f"  │   ├── info.json")
    print(f"  │   ├── tasks.jsonl")
    print(f"  │   ├── episodes.jsonl")
    print(f"  │   └── episodes_stats.jsonl")
    print(f"  ├── data/")
    print(f"  │   └── chunk-000/")
    print(f"  │       └── episode_000000.parquet")
    print(f"  └── videos/")
    print(f"      └── chunk-000/")
    print(f"          ├── observation.images.cam_env/")
    print(f"          ├── observation.images.cam_left_wrist/")
    print(f"          └── observation.images.cam_right_wrist/")


def main(
    hdf5_path: Path,
    output_dir: Path,
    robot_type: str = "limx Tron2",
    fps: int = 30,
    task: str = "Fold the laundry"
):
    """Main entry point."""
    convert_hdf5_to_lerobot_v21(hdf5_path, output_dir, robot_type, fps, task)


if __name__ == "__main__":
    tyro.cli(main)
