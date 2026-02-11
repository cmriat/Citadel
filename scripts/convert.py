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
from typing import Dict, List, Tuple
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


def align_data_to_reference(ref_timestamps, data, data_timestamps, data_name, method='nearest'):
    """通用的时间对齐函数

    Args:
        ref_timestamps: [N_ref] 参考时间戳
        data: [N_data, ...] 待对齐数据 (可以是图像或关节)
        data_timestamps: [N_data] 数据时间戳
        data_name: 数据名称 (用于日志)
        method: 对齐方法 - 'nearest' (最近邻) 或 'linear' (线性插值)

    Returns:
        aligned_data: [N_ref, ...] 对齐后的数据
    """
    if method == 'nearest':
        # 最近邻对齐（原方法）
        aligned_indices = []
        for ref_ts in ref_timestamps:
            closest_idx = np.argmin(np.abs(data_timestamps - ref_ts))
            aligned_indices.append(closest_idx)
        aligned_data = data[aligned_indices]

    elif method == 'linear':
        # 线性插值对齐
        from scipy.interpolate import interp1d

        # 对于多维数据，需要逐维度插值
        if data.ndim == 1:
            interp_func = interp1d(
                data_timestamps, data,
                kind='linear',
                bounds_error=False,
                fill_value=(data[0], data[-1])  # 边界使用首尾值
            )
            aligned_data = interp_func(ref_timestamps)
        else:
            # 多维数据：对每个维度分别插值
            aligned_data = np.zeros((len(ref_timestamps),) + data.shape[1:], dtype=data.dtype)
            for i in range(data.shape[1]):
                interp_func = interp1d(
                    data_timestamps, data[:, i],
                    kind='linear',
                    bounds_error=False,
                    fill_value=(data[0, i], data[-1, i])
                )
                aligned_data[:, i] = interp_func(ref_timestamps)
    else:
        raise ValueError(f"Unknown alignment method: {method}. Supported: 'nearest', 'linear'")

    # 计算对齐质量（基于最近邻误差）
    nearest_indices = [np.argmin(np.abs(data_timestamps - ts)) for ts in ref_timestamps]
    time_errors = np.abs(data_timestamps[nearest_indices] - ref_timestamps)
    print(f"  {data_name}: method={method}, 平均误差={np.mean(time_errors)/1e6:.2f}ms, 最大误差={np.max(time_errors)/1e6:.2f}ms")

    return aligned_data


def detect_gap_segments(
    reference_timestamps: np.ndarray,
    cameras_info: Dict[str, np.ndarray],
    gap_factor: float = 5.0,
    min_segment_frames: int = 30
) -> List[np.ndarray]:
    """检测所有相机的严重跳帧，将 reference_timestamps 切割为有效片段。

    Args:
        reference_timestamps: 基准时间戳数组
        cameras_info: {相机名: 时间戳数组}
        gap_factor: 帧间隔超过 median_interval * gap_factor 视为跳帧
        min_segment_frames: 最小有效片段帧数

    Returns:
        有效片段的 reference_timestamps 列表（每个元素是一个连续时间段的时间戳数组）
        空列表表示整个 episode 不可用
    """
    # 1. 收集所有相机的跳帧区间
    all_gap_intervals: List[Tuple[float, float]] = []

    for cam_name, cam_ts in cameras_info.items():
        if len(cam_ts) < 2:
            continue
        intervals = np.diff(cam_ts)
        median_interval = np.median(intervals)
        gap_threshold = median_interval * gap_factor

        gap_indices = np.where(intervals > gap_threshold)[0]
        for idx in gap_indices:
            gap_start_ts = cam_ts[idx]
            gap_end_ts = cam_ts[idx + 1]
            gap_duration_ms = (gap_end_ts - gap_start_ts) / 1e6
            print(f"  ⚡ {cam_name}: 跳帧 @ idx={idx}, 间隔={gap_duration_ms:.1f}ms "
                  f"(阈值={gap_threshold/1e6:.1f}ms)")
            all_gap_intervals.append((gap_start_ts, gap_end_ts))

    # 无跳帧 → 返回完整时间戳
    if not all_gap_intervals:
        print("  ✅ 无严重跳帧，保留完整 episode")
        return [reference_timestamps]

    # 2. 合并重叠的跳帧区间（union）
    all_gap_intervals.sort(key=lambda x: x[0])
    merged: List[Tuple[float, float]] = [all_gap_intervals[0]]
    for start, end in all_gap_intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # 3. 用跳帧区间切割 reference_timestamps
    #    在跳帧区间内的参考帧全部丢弃，区间外的帧形成连续片段
    segments: List[np.ndarray] = []
    current_mask = np.ones(len(reference_timestamps), dtype=bool)

    for gap_start, gap_end in merged:
        # 标记落在跳帧区间内的参考帧为无效
        in_gap = (reference_timestamps >= gap_start) & (reference_timestamps <= gap_end)
        current_mask &= ~in_gap

    # 从有效帧中提取连续片段
    valid_indices = np.where(current_mask)[0]
    if len(valid_indices) == 0:
        print("  ❌ 所有帧均在跳帧区间内，episode 不可用")
        return []

    # 检测连续索引的断点（非连续处即为切割点）
    breaks = np.where(np.diff(valid_indices) > 1)[0] + 1
    index_groups = np.split(valid_indices, breaks)

    for group in index_groups:
        seg_ts = reference_timestamps[group]
        segments.append(seg_ts)

    # 4. 过滤掉帧数不足的片段
    valid_segments = []
    for i, seg in enumerate(segments):
        if len(seg) >= min_segment_frames:
            valid_segments.append(seg)
        else:
            print(f"  🗑️  片段 {i}: {len(seg)} 帧 < {min_segment_frames} 帧阈值，丢弃")

    # 5. 打印切割报告
    print(f"\n  📊 跳帧切割报告:")
    print(f"     检测到 {len(merged)} 个跳帧区间")
    print(f"     切割为 {len(segments)} 个片段，有效 {len(valid_segments)} 个")
    for i, seg in enumerate(valid_segments):
        duration_s = (seg[-1] - seg[0]) / 1e9
        print(f"     片段 {i}: {len(seg)} 帧, {duration_s:.2f}s")

    return valid_segments


def map_master_eef_to_slave_mapping(master_eef: np.ndarray, slave_mapping_stats: dict) -> np.ndarray:
    """将master的eef_gripper_joint_pos映射到slave的gripper_mapping_controller_pos范围

    Args:
        master_eef: [N, 1] master的eef夹爪原始值
        slave_mapping_stats: slave mapping的统计信息 {'min': float, 'max': float}

    Returns:
        mapped_values: [N, 1] 映射后的值，范围与slave_mapping一致

    注意：master_eef和slave_mapping的物理意义相反：
        - master_eef: 小值=打开, 大值=闭合
        - slave_mapping: 小值=闭合, 大值=打开
        因此需要反向映射：master_min->target_max, master_max->target_min
    """
    # 计算master_eef的范围（使用当前数据的实际范围）
    master_min = master_eef.min()
    master_max = master_eef.max()

    # 获取目标范围（slave_mapping）
    target_min = slave_mapping_stats['min']
    target_max = slave_mapping_stats['max']

    # 反向线性映射：master_min（打开）-> target_max（打开）, master_max（闭合）-> target_min（闭合）
    # y = target_max - (x - x_min) / (x_max - x_min) * (y_max - y_min)
    mapped = target_max - (master_eef - master_min) / (master_max - master_min + 1e-8) * \
             (target_max - target_min)

    return mapped


def load_episode_v1_format(
    ep_path: Path,
    alignment_method: str = 'nearest',
    gap_factor: float = 5.0,
    min_segment_frames: int = 30
) -> List[Dict]:
    """加载online_test_hdf5_v1格式的Episode数据，支持跳帧切割

    当某相机出现严重跳帧时，在跳帧处切割 episode，保留所有有效片段
    作为独立的 sub-episode 输出，最大化真机数据利用率。

    数据格式:
        images/cam_env/frames_jpeg - JPEG压缩图像
        joints/{left|right}_{master|slave}/joint{1-6}_pos
        joints/{left|right}_{master|slave}/eef_gripper_joint_pos

    Args:
        ep_path: HDF5文件路径
        alignment_method: 对齐方法 - 'nearest' (最近邻) 或 'linear' (线性插值)
        gap_factor: 跳帧判定倍数，帧间隔 > 正常间隔 × gap_factor 视为严重跳帧
        min_segment_frames: 最小有效片段帧数，低于此阈值丢弃

    Returns:
        有效片段列表，每个元素为:
        {
            'images_env': [N, H, W, 3] uint8,
            'images_left_wrist': [N, H, W, 3] uint8,
            'images_right_wrist': [N, H, W, 3] uint8,
            'state': [N, 14] float32,
            'action': [N, 14] float32
        }
        空列表表示整个 episode 不可用
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
        N_frames_original = len(reference_timestamps)

        print(f"\n⏱️  时间对齐基准: {min_camera} ({N_frames_original}帧)")

        # ========== 1.5 自适应边界裁剪 ==========
        print("\n✂️  自适应边界裁剪:")

        # 预读所有关节数据源的时间戳以计算边界
        joint_groups = ["joints/left_slave", "joints/right_slave"]
        has_master = "left_master" in f["joints"]
        if has_master:
            joint_groups += ["joints/left_master", "joints/right_master"]

        all_joint_end_ts = []
        for grp in joint_groups:
            sec = f[f"{grp}/timestamp_sec"][:]
            nsec = f[f"{grp}/timestamp_nanosec"][:]
            ts = sec * 1e9 + nsec
            all_joint_end_ts.append(ts[-1])

        # 用 left_slave 计算头帧时延（估算图像与关节的固有延迟）
        left_slave_ts = (f["joints/left_slave/timestamp_sec"][:] * 1e9
                         + f["joints/left_slave/timestamp_nanosec"][:])
        img_first_ts = reference_timestamps[0]
        joint_nearest_idx = np.argmin(np.abs(left_slave_ts - img_first_ts))
        joint_nearest_ts = left_slave_ts[joint_nearest_idx]
        head_delay_ns = img_first_ts - joint_nearest_ts
        head_delay_ms = head_delay_ns / 1e6

        print(f"  头帧时延: {head_delay_ms:+.2f} ms (图像{'晚于' if head_delay_ns >= 0 else '早于'}关节)")

        # 取所有关节源中最早结束的时间戳，确保所有数据源都有覆盖
        joint_end_ts = min(all_joint_end_ts)
        print(f"  关节数据源: {len(joint_groups)} 组, 最早结束: {joint_end_ts/1e9:.3f}s")
        tolerance_end_ts = joint_end_ts + abs(head_delay_ns)  # 使用绝对值，确保容忍度为正

        # 计算基准相机的有效帧掩码
        valid_mask = reference_timestamps <= tolerance_end_ts

        # 统计裁剪情况
        trimmed_end = np.sum(reference_timestamps > tolerance_end_ts)

        if trimmed_end > 0:
            # 计算超出部分的时间
            exceeded_frames = reference_timestamps[~valid_mask]
            max_exceed_ms = (exceeded_frames[-1] - tolerance_end_ts) / 1e6 if len(exceeded_frames) > 0 else 0

            print(f"  结束边界容忍: joint_end + {abs(head_delay_ms):.2f}ms")
            print(f"  裁剪帧数: {trimmed_end} 帧 (超出容忍度 {max_exceed_ms:.2f}ms)")

            # 裁剪基准相机的参考时间戳
            reference_timestamps = reference_timestamps[valid_mask]
            N_frames = len(reference_timestamps)
            print(f"  保留帧数: {N_frames} / {N_frames_original}")
        else:
            N_frames = N_frames_original
            print(f"  无需裁剪，所有 {N_frames_original} 帧在容忍度内")

        # ========== 1.6 跳帧切割 ==========
        print("\n🔍 跳帧检测:")
        segments = detect_gap_segments(
            reference_timestamps, cameras_info,
            gap_factor=gap_factor,
            min_segment_frames=min_segment_frames
        )

        if not segments:
            print("\n❌ Episode 无有效片段")
            return []

        # ========== 2. 全量解码图像（只做一次） ==========
        print("\n📸 图像解码:")
        images_env_raw = decode_jpeg_frames(f, "cam_env")
        print(f"  cam_env: {images_env_raw.shape}")
        images_left_raw = decode_jpeg_frames(f, "cam_left_wrist")
        print(f"  cam_left_wrist: {images_left_raw.shape}")
        images_right_raw = decode_jpeg_frames(f, "cam_right_wrist")
        print(f"  cam_right_wrist: {images_right_raw.shape}")

        # ========== 3. 读取全量关节原始数据（只做一次） ==========
        # 3.1 left slave
        left_joints_raw = reconstruct_joint_vector(f["joints/left_slave"], 6)
        left_gripper_raw = f["joints/left_slave/gripper_mapping_controller_pos"][:][:, np.newaxis]
        left_joint_sec = f["joints/left_slave/timestamp_sec"][:]
        left_joint_nsec = f["joints/left_slave/timestamp_nanosec"][:]
        left_joint_timestamps = left_joint_sec * 1e9 + left_joint_nsec

        # 3.2 right slave
        right_joints_raw = reconstruct_joint_vector(f["joints/right_slave"], 6)
        right_gripper_raw = f["joints/right_slave/gripper_mapping_controller_pos"][:][:, np.newaxis]
        right_joint_sec = f["joints/right_slave/timestamp_sec"][:]
        right_joint_nsec = f["joints/right_slave/timestamp_nanosec"][:]
        right_joint_timestamps = right_joint_sec * 1e9 + right_joint_nsec

        # 3.3 master（如果存在）
        if has_master:
            left_joints_cmd_raw = reconstruct_joint_vector(f["joints/left_master"], 6)
            left_gripper_cmd_raw = f["joints/left_master/eef_gripper_joint_pos"][:][:, np.newaxis]
            left_slave_mapping = f["joints/left_slave/gripper_mapping_controller_pos"][:]
            left_mapping_stats = {'min': left_slave_mapping.min(), 'max': left_slave_mapping.max()}
            left_cmd_sec = f["joints/left_master/timestamp_sec"][:]
            left_cmd_nsec = f["joints/left_master/timestamp_nanosec"][:]
            left_cmd_timestamps = left_cmd_sec * 1e9 + left_cmd_nsec

            right_joints_cmd_raw = reconstruct_joint_vector(f["joints/right_master"], 6)
            right_gripper_cmd_raw = f["joints/right_master/eef_gripper_joint_pos"][:][:, np.newaxis]
            right_slave_mapping = f["joints/right_slave/gripper_mapping_controller_pos"][:]
            right_mapping_stats = {'min': right_slave_mapping.min(), 'max': right_slave_mapping.max()}
            right_cmd_sec = f["joints/right_master/timestamp_sec"][:]
            right_cmd_nsec = f["joints/right_master/timestamp_nanosec"][:]
            right_cmd_timestamps = right_cmd_sec * 1e9 + right_cmd_nsec

        # ========== 4. 对每个 segment 独立执行对齐和组装 ==========
        results: List[Dict] = []

        for seg_idx, seg_timestamps in enumerate(segments):
            seg_label = f"片段 {seg_idx}" if len(segments) > 1 else "完整 episode"
            print(f"\n{'='*60}")
            print(f"📦 处理 {seg_label} ({len(seg_timestamps)} 帧)")
            print(f"{'='*60}")

            # 4.1 图像对齐
            print("\n📸 图像对齐:")
            seg_images_env = align_data_to_reference(
                seg_timestamps, images_env_raw, cameras_info['cam_env'],
                'cam_env', method='nearest'
            )
            seg_images_left = align_data_to_reference(
                seg_timestamps, images_left_raw, cameras_info['cam_left_wrist'],
                'cam_left_wrist', method='nearest'
            )
            seg_images_right = align_data_to_reference(
                seg_timestamps, images_right_raw, cameras_info['cam_right_wrist'],
                'cam_right_wrist', method='nearest'
            )

            # 4.2 关节对齐
            print("\n🦾 关节对齐:")
            seg_left_joints = align_data_to_reference(
                seg_timestamps, left_joints_raw, left_joint_timestamps,
                'left_joints', method=alignment_method
            )
            seg_left_gripper = align_data_to_reference(
                seg_timestamps, left_gripper_raw, left_joint_timestamps,
                'left_gripper', method=alignment_method
            )
            seg_right_joints = align_data_to_reference(
                seg_timestamps, right_joints_raw, right_joint_timestamps,
                'right_joints', method=alignment_method
            )
            seg_right_gripper = align_data_to_reference(
                seg_timestamps, right_gripper_raw, right_joint_timestamps,
                'right_gripper', method=alignment_method
            )

            # 4.3 组装 State (14维)
            state = np.concatenate([
                seg_left_joints,   # [N, 6]
                seg_left_gripper,  # [N, 1]
                seg_right_joints,  # [N, 6]
                seg_right_gripper  # [N, 1]
            ], axis=1).astype(np.float32)

            # 4.4 组装 Action (14维)
            if has_master:
                print("\n🎮 动作对齐:")
                seg_left_joints_cmd = align_data_to_reference(
                    seg_timestamps, left_joints_cmd_raw, left_cmd_timestamps,
                    'left_joints_cmd', method=alignment_method
                )
                seg_left_gripper_cmd_aligned = align_data_to_reference(
                    seg_timestamps, left_gripper_cmd_raw, left_cmd_timestamps,
                    'left_gripper_cmd', method=alignment_method
                )
                seg_right_joints_cmd = align_data_to_reference(
                    seg_timestamps, right_joints_cmd_raw, right_cmd_timestamps,
                    'right_joints_cmd', method=alignment_method
                )
                seg_right_gripper_cmd_aligned = align_data_to_reference(
                    seg_timestamps, right_gripper_cmd_raw, right_cmd_timestamps,
                    'right_gripper_cmd', method=alignment_method
                )

                seg_left_gripper_cmd = map_master_eef_to_slave_mapping(
                    seg_left_gripper_cmd_aligned, left_mapping_stats
                )
                seg_right_gripper_cmd = map_master_eef_to_slave_mapping(
                    seg_right_gripper_cmd_aligned, right_mapping_stats
                )

                print(f"  ✓ 夹爪映射: master_eef -> slave_mapping 范围")

                action = np.concatenate([
                    seg_left_joints_cmd,
                    seg_left_gripper_cmd,
                    seg_right_joints_cmd,
                    seg_right_gripper_cmd
                ], axis=1).astype(np.float32)

                print(f"  ✅ 使用master数据作为action (夹爪已映射)")
            else:
                action = state.copy()
                print(f"\n  ⚠️  警告: master数据不存在，复制slave作为action")

            results.append({
                'images_env': seg_images_env,
                'images_left_wrist': seg_images_left,
                'images_right_wrist': seg_images_right,
                'state': state,
                'action': action
            })

        # ========== 5. 汇总报告 ==========
        total_frames = sum(len(r['state']) for r in results)
        print(f"\n✅ 数据加载完成: {len(results)} 个片段, 共 {total_frames} 帧\n")

        return results


def encode_video_frames(frames: np.ndarray, output_path: Path, fps: int = 30):
    """Encode RGB frame sequence to MP4 video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    container = av.open(str(output_path), mode='w')
    stream = container.add_stream('h264', rate=fps)
    stream.width = frames.shape[2]   # W from [N, H, W, C]
    stream.height = frames.shape[1]  # H from [N, H, W, C]
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
    total_episodes: int,
    fps: int,
    robot_type: str,
    dataset_name: str,
    image_height: int = 480,
    image_width: int = 640
):
    """Generate info.json metadata file in meta/ directory."""
    info = {
        "codebase_version": "v2.1",
        "robot_type": robot_type,
        "total_episodes": total_episodes,
        "total_frames": total_frames,
        "total_tasks": 1,
        "total_videos": 3 * total_episodes,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": fps,
        "splits": {
            "train": f"0:{total_episodes}"
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
                "shape": [image_height, image_width, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": image_height,
                    "video.width": image_width,
                    "video.codec": "libx264",
                    "video.pix_fmt": "yuv420p",
                    "video.is_depth_map": False,
                    "video.fps": fps,
                    "video.channels": 3,
                    "has_audio": False
                }
            },
            "observation.images.cam_left_wrist": {
                "dtype": "video",
                "shape": [image_height, image_width, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": image_height,
                    "video.width": image_width,
                    "video.codec": "libx264",
                    "video.pix_fmt": "yuv420p",
                    "video.is_depth_map": False,
                    "video.fps": fps,
                    "video.channels": 3,
                    "has_audio": False
                }
            },
            "observation.images.cam_right_wrist": {
                "dtype": "video",
                "shape": [image_height, image_width, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": image_height,
                    "video.width": image_width,
                    "video.codec": "libx264",
                    "video.pix_fmt": "yuv420p",
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


def generate_episodes_jsonl(output_dir: Path, episodes_info: List[Dict], task: str):
    """Generate episodes.jsonl metadata file in meta/ directory.

    Args:
        output_dir: 输出目录
        episodes_info: [{'episode_index': int, 'num_frames': int}, ...]
        task: 任务描述
    """
    with open(output_dir / "meta" / "episodes.jsonl", "w") as f:
        for ep_info in episodes_info:
            f.write(json.dumps({
                "episode_index": ep_info['episode_index'],
                "tasks": [task],
                "length": ep_info['num_frames']
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
    task: str = "Fold the laundry",
    alignment_method: str = "nearest",
    gap_factor: float = 5.0,
    min_segment_frames: int = 30
):
    """Convert HDF5 episode to LeRobot v2.1 format.

    支持跳帧切割：当某相机出现严重跳帧时，在跳帧处切割 episode，
    保留所有有效片段作为独立的 sub-episode 输出。

    Args:
        hdf5_path: HDF5文件路径
        output_dir: 输出目录
        robot_type: 机器人类型
        fps: 视频帧率
        task: 任务描述
        alignment_method: 对齐方法 - 'nearest' (最近邻) 或 'linear' (线性插值)
        gap_factor: 跳帧判定倍数，帧间隔 > 正常间隔 × gap_factor 视为严重跳帧
        min_segment_frames: 最小有效片段帧数，低于此阈值丢弃
    """
    dataset_name = output_dir.name
    print(f"Converting {hdf5_path} to LeRobot v2.1 format...")
    print(f"Output directory: {output_dir}")
    print(f"Dataset name: {dataset_name}")
    print(f"Alignment method: {alignment_method}")
    print(f"Gap detection: factor={gap_factor}, min_frames={min_segment_frames}")

    # 1. Create output directory structure
    create_output_structure(output_dir)

    # 2. Load HDF5 data (returns list of segments)
    print("\nLoading HDF5 data...")
    segments = load_episode_v1_format(
        hdf5_path,
        alignment_method=alignment_method,
        gap_factor=gap_factor,
        min_segment_frames=min_segment_frames
    )

    if not segments:
        print("\n⚠️  Episode 无有效片段，跳过")
        return

    num_episodes = len(segments)
    total_frames = sum(len(seg['state']) for seg in segments)
    print(f"\nLoaded {num_episodes} segment(s), {total_frames} total frames")

    # 3. 为每个 segment 输出独立的 episode 文件
    episodes_info = []
    all_stats = []

    for ep_idx, episode_data in enumerate(segments):
        num_frames = len(episode_data['state'])
        ep_tag = f"episode_{ep_idx:06d}"
        print(f"\n{'='*60}")
        print(f"📦 输出 {ep_tag} ({num_frames} 帧)")
        print(f"{'='*60}")

        # 3.1 Encode videos
        print("  Encoding videos...")
        for cam_key in ['cam_env', 'cam_left_wrist', 'cam_right_wrist']:
            video_path = output_dir / "videos" / "chunk-000" / \
                         f"observation.images.{cam_key}" / f"{ep_tag}.mp4"

            images_key = f"images_{cam_key.replace('cam_', '')}"
            print(f"    {cam_key}... ", end="", flush=True)
            encode_video_frames(episode_data[images_key], video_path, fps)
            print(f"✓ {video_path.stat().st_size / 1024 / 1024:.1f} MB")

        # 3.2 Generate Parquet data file
        parquet_path = output_dir / "data" / "chunk-000" / f"{ep_tag}.parquet"
        create_episode_parquet(episode_data, parquet_path, episode_index=ep_idx, fps=fps)
        print(f"  ✓ {parquet_path}")

        # 3.3 Compute episode statistics
        stats = compute_episode_stats(episode_data, episode_index=ep_idx, fps=fps)
        all_stats.append(stats)

        episodes_info.append({
            'episode_index': ep_idx,
            'num_frames': num_frames
        })

    # 4. Generate metadata files
    print("\nGenerating metadata files...")
    image_height = segments[0]['images_env'].shape[1]
    image_width = segments[0]['images_env'].shape[2]
    generate_info_json(output_dir, total_frames, num_episodes, fps, robot_type, dataset_name,
                       image_height=image_height, image_width=image_width)
    print("  ✓ meta/info.json")

    generate_tasks_jsonl(output_dir, task)
    print("  ✓ meta/tasks.jsonl")

    generate_episodes_jsonl(output_dir, episodes_info, task)
    print("  ✓ meta/episodes.jsonl")

    generate_episodes_stats_jsonl(output_dir, all_stats)
    print("  ✓ meta/episodes_stats.jsonl")

    print(f"\n✅ Conversion complete!")
    print(f"   Output: {output_dir}")
    print(f"   Episodes: {num_episodes}")
    print(f"   Total frames: {total_frames}")
    for ep_info in episodes_info:
        print(f"     episode_{ep_info['episode_index']:06d}: {ep_info['num_frames']} frames")
    print(f"   Videos: {3 * num_episodes}")


def main(
    hdf5_path: Path,
    output_dir: Path,
    robot_type: str = "limx Tron2",
    fps: int = 30,
    task: str = "Fold the laundry",
    alignment_method: str = "nearest",
    gap_factor: float = 5.0,
    min_segment_frames: int = 30
):
    """Main entry point.

    Args:
        hdf5_path: HDF5文件路径
        output_dir: 输出目录
        robot_type: 机器人类型
        fps: 视频帧率
        task: 任务描述
        alignment_method: 关节对齐方法 - 'nearest' (最近邻) 或 'linear' (线性插值)
        gap_factor: 跳帧判定倍数，帧间隔 > 正常间隔 × gap_factor 视为严重跳帧
        min_segment_frames: 最小有效片段帧数，低于此阈值丢弃
    """
    convert_hdf5_to_lerobot_v21(
        hdf5_path, output_dir, robot_type, fps, task,
        alignment_method, gap_factor, min_segment_frames
    )


if __name__ == "__main__":
    tyro.cli(main)
