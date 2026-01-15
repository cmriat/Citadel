"""
过滤 LeRobot 数据集，移除不完整和异常的 episode。

包含四种检测类型（全部强制执行）：
1. 完整性检测：结束状态在 IQR 边界内
2. 跳变检测：无突然的关节角度变化
3. 关节有效性：关节必须有运动（std > 阈值）
4. 视频有效性：视频必须有画面变化（帧差 > 阈值）

=== 阈值参考 ===

1. jump_threshold（默认：0.2 rad ≈ 11.5°）
   - 检测连续帧之间的突然跳变
   - 如果任一关节帧间变化 > 阈值，episode 被拒绝
   - 值越小 = 越严格（捕捉更小的跳变）
   - 典型范围：0.1 ~ 0.3 rad

2. iqr_factor（默认：1.5）
   - 结束状态异常值检测的 IQR 乘数
   - 边界：[Q1 - factor*IQR, Q3 + factor*IQR]
   - 1.5 = 标准异常值，3.0 = 极端异常值
   - 值越大 = 越宽松

   【IQR 说明】
   IQR (Interquartile Range) = 四分位距 = Q3 - Q1
   - Q1 = 第25百分位数（下四分位）
   - Q3 = 第75百分位数（上四分位）

   原理：收集所有 episode 的结束状态，计算正常范围。
   大多数 episode 结束时机械臂位置相似（如回到原点），
   如果某个 episode 结束位置明显偏离（如中途中断），会被检测出来。

3. joint_std_threshold（默认：0.01 rad ≈ 0.57°）
   - 每个关节的最小标准差
   - 如果任一关节的 std < 阈值，episode 被拒绝（关节静止）
   - 值越小 = 越宽松（允许更少的运动）
   - 典型范围：0.005 ~ 0.02 rad

4. video_motion_threshold（默认：1.0）
   - 帧间 RGB 差分均值阈值
   - 如果均值差 < 阈值，视频被认为是静止的
   - 静态场景通常 < 0.5，正常运动 > 2.0
   - 值越小 = 越宽松

使用方法：
    pixi run filter /path/to/input /path/to/output
    pixi run filter /path/to/input /path/to/output --jump-threshold 0.15 --joint-std-threshold 0.02
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import av
import numpy as np
import pyarrow.parquet as pq


# Joint indices (excluding gripper)
LEFT_JOINT_DIMS = list(range(0, 6))   # dim 0-5
RIGHT_JOINT_DIMS = list(range(7, 13)) # dim 7-12
JOINT_DIMS = LEFT_JOINT_DIMS + RIGHT_JOINT_DIMS

# Gripper indices
LEFT_GRIPPER_DIM = 6
RIGHT_GRIPPER_DIM = 13
GRIPPER_DIMS = [LEFT_GRIPPER_DIM, RIGHT_GRIPPER_DIM]


def load_parquet_state(parquet_path: Path) -> Optional[np.ndarray]:
    """Load state data from parquet file."""
    try:
        table = pq.read_table(parquet_path)
        state = np.array(table["observation.state"].to_pylist())
        return state
    except Exception as e:
        print(f"  ⚠️  Failed to load {parquet_path}: {e}")
        return None


def find_parquet_file(episode_dir: Path) -> Optional[Path]:
    """Find parquet file in episode directory."""
    candidates = [
        episode_dir / "data" / "chunk-000" / "episode_000000.parquet",
        episode_dir / "chunk-000" / "episode_000000.parquet",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Fallback: glob search
    parquets = list(episode_dir.glob("**/*.parquet"))
    return parquets[0] if parquets else None


def compute_iqr_bounds(
    values: np.ndarray,
    factor: float = 1.5
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute IQR-based bounds for outlier detection.

    Args:
        values: [N, D] array of values
        factor: IQR multiplier (1.5 = standard, 3.0 = extreme)

    Returns:
        (lower_bounds, upper_bounds) arrays of shape [D]
    """
    q1 = np.percentile(values, 25, axis=0)
    q3 = np.percentile(values, 75, axis=0)
    iqr = q3 - q1

    lower = q1 - factor * iqr
    upper = q3 + factor * iqr

    return lower, upper


def check_completeness(
    end_state: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    exclude_gripper: bool = True
) -> tuple[bool, list[int]]:
    """
    Check if episode end state is within normal bounds.

    Returns:
        (is_complete, outlier_dims)
    """
    dims_to_check = JOINT_DIMS if exclude_gripper else list(range(len(end_state)))

    outlier_dims = []
    for dim in dims_to_check:
        if end_state[dim] < lower_bounds[dim] or end_state[dim] > upper_bounds[dim]:
            outlier_dims.append(dim)

    return len(outlier_dims) == 0, outlier_dims


def check_jumps(
    state: np.ndarray,
    threshold: float = 0.2,
    exclude_gripper: bool = True
) -> tuple[bool, float, int, list[int]]:
    """
    Detect sudden jumps between consecutive frames.

    Returns:
        (has_jump, max_jump, jump_count, jump_frames)
    """
    dims_to_check = JOINT_DIMS if exclude_gripper else list(range(state.shape[1]))

    # Extract relevant dimensions
    state_subset = state[:, dims_to_check]

    # Compute frame-to-frame differences
    diff = np.abs(np.diff(state_subset, axis=0))

    # Find jumps exceeding threshold
    max_diff_per_frame = np.max(diff, axis=1)
    jump_mask = max_diff_per_frame > threshold

    max_jump = float(np.max(diff)) if diff.size > 0 else 0.0
    jump_count = int(np.sum(jump_mask))
    jump_frames = np.where(jump_mask)[0].tolist()

    return jump_count > 0, max_jump, jump_count, jump_frames


def check_joint_validity(
    state: np.ndarray,
    std_threshold: float = 0.01,
    exclude_gripper: bool = True
) -> tuple[bool, dict]:
    """
    Check if joints have valid movement (not static).

    Computes std for each joint dimension. If any joint has std < threshold,
    the episode is considered invalid (static).

    Args:
        state: [N, D] joint state array
        std_threshold: Minimum std threshold in radians (default: 0.01 ~0.57°)
        exclude_gripper: Whether to exclude gripper dimensions

    Returns:
        (is_valid, details)
        - is_valid: True if all joints have std >= threshold
        - details: dict with joint_stds, invalid_joints, min_std
    """
    dims_to_check = JOINT_DIMS if exclude_gripper else list(range(state.shape[1]))

    # Extract joint data
    joint_data = state[:, dims_to_check]

    # Compute std for each joint
    joint_stds = np.std(joint_data, axis=0)

    # Find invalid joints (std < threshold)
    invalid_mask = joint_stds < std_threshold
    invalid_joints = [dims_to_check[i] for i, inv in enumerate(invalid_mask) if inv]

    is_valid = len(invalid_joints) == 0

    return is_valid, {
        "joint_stds": [round(s, 6) for s in joint_stds.tolist()],
        "invalid_joints": invalid_joints,
        "min_std": round(float(np.min(joint_stds)), 6)
    }


# Camera names for video validity check
CAMERA_NAMES = ["cam_env", "cam_left_wrist", "cam_right_wrist"]


def find_video_files(episode_dir: Path) -> dict[str, Optional[Path]]:
    """
    Find video files for each camera in episode directory.

    Args:
        episode_dir: Episode directory path

    Returns:
        Dict mapping camera name to video path (or None if not found)
    """
    video_paths = {}

    for cam in CAMERA_NAMES:
        # Try common path patterns
        candidates = [
            episode_dir / "videos" / "chunk-000" / f"observation.images.{cam}" / "episode_000000.mp4",
            episode_dir / "chunk-000" / f"observation.images.{cam}" / "episode_000000.mp4",
        ]

        found = None
        for candidate in candidates:
            if candidate.exists():
                found = candidate
                break

        # Fallback: glob search
        if found is None:
            matches = list(episode_dir.glob(f"**/observation.images.{cam}/*.mp4"))
            if matches:
                found = matches[0]

        video_paths[cam] = found

    return video_paths


def check_video_validity(
    video_path: Path,
    motion_threshold: float = 1.0,
    sample_rate: int = 5,
    max_samples: int = 100
) -> tuple[bool, dict]:
    """
    Check if video has motion (not static).

    Uses frame difference method: computes mean absolute difference
    between consecutive sampled frames.

    Args:
        video_path: Path to video file
        motion_threshold: Motion threshold for mean frame diff (default: 1.0)
        sample_rate: Sample every N frames (default: 5)
        max_samples: Maximum frames to sample (default: 100)

    Returns:
        (is_valid, details)
        - is_valid: True if video has sufficient motion
        - details: dict with mean_diff, max_diff, frame_count, samples
    """
    try:
        container = av.open(str(video_path))
        stream = container.streams.video[0]

        frame_count = stream.frames or 0
        prev_frame = None
        diffs = []
        sample_idx = 0

        for frame in container.decode(stream):
            if sample_idx % sample_rate == 0:
                # Convert to numpy array
                current = frame.to_ndarray(format='rgb24').astype(np.float32)

                if prev_frame is not None:
                    # Compute mean absolute difference
                    diff = np.abs(current - prev_frame).mean()
                    diffs.append(diff)

                prev_frame = current

                if len(diffs) >= max_samples:
                    break

            sample_idx += 1

        container.close()

        if not diffs:
            return False, {
                "error": "no_frames",
                "frame_count": frame_count
            }

        mean_diff = float(np.mean(diffs))
        max_diff = float(np.max(diffs))
        is_valid = mean_diff >= motion_threshold

        return is_valid, {
            "mean_diff": round(mean_diff, 4),
            "max_diff": round(max_diff, 4),
            "frame_count": frame_count,
            "samples": len(diffs)
        }

    except Exception as e:
        return False, {"error": str(e)}


def check_all_videos_validity(
    episode_dir: Path,
    motion_threshold: float = 1.0,
    sample_rate: int = 5,
    max_samples: int = 100
) -> tuple[bool, dict]:
    """
    Check validity of all camera videos. Any static camera marks episode as invalid.

    Args:
        episode_dir: Episode directory path
        motion_threshold: Motion threshold for mean frame diff
        sample_rate: Sample every N frames
        max_samples: Maximum frames to sample per video

    Returns:
        (is_valid, details)
        - is_valid: True if all camera videos have motion
        - details: dict with per-camera results and static_cameras list
    """
    video_paths = find_video_files(episode_dir)
    results = {}
    static_cameras = []

    for cam, path in video_paths.items():
        if path is None:
            results[cam] = {"error": "not_found"}
            static_cameras.append(cam)
            continue

        is_valid, details = check_video_validity(
            path, motion_threshold, sample_rate, max_samples
        )
        results[cam] = details

        if not is_valid:
            static_cameras.append(cam)

    all_valid = len(static_cameras) == 0

    return all_valid, {
        **results,
        "static_cameras": static_cameras
    }


def filter_episodes(
    input_dir: Path,
    output_dir: Path,
    jump_threshold: float = 0.2,
    iqr_factor: float = 1.5,
    exclude_gripper: bool = True,
    use_symlink: bool = True,
    # Joint validity parameters
    joint_std_threshold: float = 0.01,
    # Video validity parameters
    video_motion_threshold: float = 1.0,
    video_sample_rate: int = 5,
    video_max_samples: int = 100
) -> dict:
    """
    Main filtering logic.

    Returns:
        Filter report dictionary
    """
    # Find all episode directories
    episode_dirs = sorted([
        d for d in input_dir.iterdir()
        if d.is_dir() and d.name.startswith("episode_")
    ])

    if not episode_dirs:
        raise ValueError(f"No episode directories found in {input_dir}")

    print(f"📂 Found {len(episode_dirs)} episodes in {input_dir}")
    print(f"📊 Parameters: jump_threshold={jump_threshold}, iqr_factor={iqr_factor}")
    print(f"📊 Joint validity: std_threshold={joint_std_threshold}")
    print(f"📊 Video validity: motion_threshold={video_motion_threshold}, sample_rate={video_sample_rate}")
    print()

    # Phase 1: Collect all end states
    print("=" * 60)
    print("Phase 1: Collecting end states...")
    print("=" * 60)

    episode_data = {}
    end_states = []

    for ep_dir in episode_dirs:
        parquet_path = find_parquet_file(ep_dir)
        if parquet_path is None:
            print(f"  ⚠️  {ep_dir.name}: No parquet file found")
            episode_data[ep_dir.name] = {"error": "no_parquet"}
            continue

        state = load_parquet_state(parquet_path)
        if state is None:
            episode_data[ep_dir.name] = {"error": "load_failed"}
            continue

        end_states.append(state[-1])
        episode_data[ep_dir.name] = {
            "path": ep_dir,
            "parquet_path": parquet_path,
            "state": state,
            "end_state": state[-1],
            "length": len(state)
        }

    if not end_states:
        raise ValueError("No valid episodes found")

    end_states = np.array(end_states)
    print(f"  ✅ Loaded {len(end_states)} episodes")

    # Phase 2: Compute IQR bounds
    print()
    print("=" * 60)
    print("Phase 2: Computing IQR bounds...")
    print("=" * 60)

    lower_bounds, upper_bounds = compute_iqr_bounds(end_states, iqr_factor)

    print(f"  IQR factor: {iqr_factor}")
    print(f"  Bounds computed for {end_states.shape[1]} dimensions")

    # Phase 3: Filter episodes
    print()
    print("=" * 60)
    print("Phase 3: Filtering episodes...")
    print("=" * 60)

    passed = []
    failed_incomplete = []
    failed_jump = []
    failed_both = []
    failed_joint_invalid = []
    failed_video_static = []
    failed_error = []

    for ep_name, data in episode_data.items():
        if "error" in data:
            failed_error.append(ep_name)
            continue

        # Check completeness
        is_complete, outlier_dims = check_completeness(
            data["end_state"], lower_bounds, upper_bounds, exclude_gripper
        )

        # Check jumps
        has_jump, max_jump, jump_count, jump_frames = check_jumps(
            data["state"], jump_threshold, exclude_gripper
        )

        # Check joint validity
        is_joint_valid, joint_validity_details = check_joint_validity(
            data["state"], joint_std_threshold, exclude_gripper
        )

        # Check video validity
        is_video_valid, video_validity_details = check_all_videos_validity(
            data["path"], video_motion_threshold, video_sample_rate, video_max_samples
        )

        # Store results
        data["is_complete"] = is_complete
        data["outlier_dims"] = outlier_dims
        data["has_jump"] = has_jump
        data["max_jump"] = max_jump
        data["jump_count"] = jump_count
        data["jump_frames"] = jump_frames[:10]  # Limit to first 10
        data["is_joint_valid"] = is_joint_valid
        data["joint_validity_details"] = joint_validity_details
        data["is_video_valid"] = is_video_valid
        data["video_validity_details"] = video_validity_details

        # Categorize: all checks must pass
        all_pass = is_complete and not has_jump and is_joint_valid and is_video_valid

        if all_pass:
            passed.append(ep_name)
        elif not is_joint_valid:
            failed_joint_invalid.append(ep_name)
        elif not is_video_valid:
            failed_video_static.append(ep_name)
        elif not is_complete and has_jump:
            failed_both.append(ep_name)
        elif not is_complete:
            failed_incomplete.append(ep_name)
        else:
            failed_jump.append(ep_name)

    print(f"  ✅ Passed: {len(passed)}")
    print(f"  ❌ Failed (incomplete): {len(failed_incomplete)}")
    print(f"  ❌ Failed (jump): {len(failed_jump)}")
    print(f"  ❌ Failed (both): {len(failed_both)}")
    print(f"  ❌ Failed (joint invalid): {len(failed_joint_invalid)}")
    print(f"  ❌ Failed (video static): {len(failed_video_static)}")
    print(f"  ⚠️  Failed (error): {len(failed_error)}")

    # Phase 4: Create output directory
    print()
    print("=" * 60)
    print("Phase 4: Creating output directory...")
    print("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    for ep_name in passed:
        src = episode_data[ep_name]["path"]
        dst = output_dir / ep_name

        if dst.exists():
            if dst.is_symlink():
                dst.unlink()
            else:
                print(f"  ⚠️  {ep_name}: Destination exists, skipping")
                continue

        if use_symlink:
            dst.symlink_to(src.resolve())
        else:
            # Copy directory (not implemented for efficiency)
            import shutil
            shutil.copytree(src, dst)

    link_type = "symlinks" if use_symlink else "copies"
    print(f"  ✅ Created {len(passed)} {link_type} in {output_dir}")

    # Phase 5: Generate report
    print()
    print("=" * 60)
    print("Phase 5: Generating report...")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "source": str(input_dir.resolve()),
        "output": str(output_dir.resolve()),
        "parameters": {
            "jump_threshold": jump_threshold,
            "iqr_factor": iqr_factor,
            "exclude_gripper": exclude_gripper,
            "use_symlink": use_symlink,
            "joint_std_threshold": joint_std_threshold,
            "video_motion_threshold": video_motion_threshold,
            "video_sample_rate": video_sample_rate,
            "video_max_samples": video_max_samples
        },
        "summary": {
            "total_episodes": len(episode_dirs),
            "passed": len(passed),
            "failed_incomplete": len(failed_incomplete),
            "failed_jump": len(failed_jump),
            "failed_both": len(failed_both),
            "failed_joint_invalid": len(failed_joint_invalid),
            "failed_video_static": len(failed_video_static),
            "failed_error": len(failed_error)
        },
        "passed_episodes": sorted(passed),
        "failed_episodes": {
            "incomplete": sorted(failed_incomplete),
            "jump": sorted(failed_jump),
            "both": sorted(failed_both),
            "joint_invalid": sorted(failed_joint_invalid),
            "video_static": sorted(failed_video_static),
            "error": sorted(failed_error)
        },
        "details": {}
    }

    # Add details for failed episodes
    all_failed = (failed_incomplete + failed_jump + failed_both +
                  failed_joint_invalid + failed_video_static)
    for ep_name in all_failed:
        data = episode_data[ep_name]
        report["details"][ep_name] = {
            "length": data["length"],
            "is_complete": data["is_complete"],
            "outlier_dims": data["outlier_dims"],
            "has_jump": data["has_jump"],
            "max_jump": round(data["max_jump"], 6),
            "jump_count": data["jump_count"],
            "jump_frames": data["jump_frames"],
            "is_joint_valid": data["is_joint_valid"],
            "joint_validity_details": data["joint_validity_details"],
            "is_video_valid": data["is_video_valid"],
            "video_validity_details": data["video_validity_details"]
        }

    report_path = output_dir / "filter_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Generate human-readable Markdown report
    md_lines = [
        "# 过滤报告",
        "",
        f"**时间**: {report['timestamp']}",
        f"**源目录**: {report['source']}",
        f"**输出目录**: {report['output']}",
        "",
        "## 统计摘要",
        "",
        f"| 类别 | 数量 | 比例 |",
        f"|------|------|------|",
        f"| ✅ 通过 | {len(passed)} | {100*len(passed)/len(episode_dirs):.1f}% |",
        f"| ❌ 未完成 (IQR) | {len(failed_incomplete)} | {100*len(failed_incomplete)/len(episode_dirs):.1f}% |",
        f"| ❌ 跳变 | {len(failed_jump)} | {100*len(failed_jump)/len(episode_dirs):.1f}% |",
        f"| ❌ 未完成+跳变 | {len(failed_both)} | {100*len(failed_both)/len(episode_dirs):.1f}% |",
        f"| ❌ 关节静止 | {len(failed_joint_invalid)} | {100*len(failed_joint_invalid)/len(episode_dirs):.1f}% |",
        f"| ❌ 视频静止 | {len(failed_video_static)} | {100*len(failed_video_static)/len(episode_dirs):.1f}% |",
        f"| ⚠️ 错误 | {len(failed_error)} | {100*len(failed_error)/len(episode_dirs):.1f}% |",
        "",
        "## 被筛掉的 Episode",
        "",
        "| Episode | 失败原因 | 详情 |",
        "|---------|----------|------|",
    ]

    # Add failed episodes with reasons
    def get_failure_reason(ep_name: str, data: dict) -> tuple[str, str]:
        """Get failure reason and details for an episode."""
        if ep_name in failed_joint_invalid:
            details = data["joint_validity_details"]
            return "关节静止", f"min_std={details['min_std']}, 静止关节={details['invalid_joints']}"
        elif ep_name in failed_video_static:
            details = data["video_validity_details"]
            return "视频静止", f"静止相机={details.get('static_cameras', [])}"
        elif ep_name in failed_both:
            return "未完成+跳变", f"异常维度={data['outlier_dims']}, max_jump={data['max_jump']:.4f}"
        elif ep_name in failed_incomplete:
            return "未完成 (IQR)", f"异常维度={data['outlier_dims']}"
        elif ep_name in failed_jump:
            return "跳变", f"max_jump={data['max_jump']:.4f}, 跳变帧={data['jump_frames'][:3]}"
        elif ep_name in failed_error:
            return "错误", str(episode_data.get(ep_name, {}).get("error", "unknown"))
        return "未知", ""

    for ep_name in sorted(all_failed + failed_error):
        if ep_name in episode_data:
            data = episode_data[ep_name]
            if "error" in data:
                reason, details = "错误", data["error"]
            else:
                reason, details = get_failure_reason(ep_name, data)
        else:
            reason, details = "错误", "数据缺失"
        md_lines.append(f"| {ep_name} | {reason} | {details} |")

    md_lines.extend(["", "---", f"*使用参数: jump={jump_threshold}, iqr={iqr_factor}, joint_std={joint_std_threshold}, video_motion={video_motion_threshold}*"])

    md_report_path = output_dir / "filter_report.md"
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"  ✅ Report saved to {report_path}")
    print(f"  ✅ Markdown report saved to {md_report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Filter LeRobot dataset by removing incomplete/anomalous episodes"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input LeRobot dataset directory"
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output directory for filtered dataset"
    )
    parser.add_argument(
        "--jump-threshold",
        type=float,
        default=0.2,
        help="Jump detection threshold in radians (default: 0.2)"
    )
    parser.add_argument(
        "--iqr-factor",
        type=float,
        default=1.5,
        help="IQR multiplier for outlier detection (default: 1.5)"
    )
    parser.add_argument(
        "--include-gripper",
        action="store_true",
        help="Include gripper dimensions in detection (default: exclude)"
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy files instead of creating symlinks"
    )
    # Joint validity parameters
    parser.add_argument(
        "--joint-std-threshold",
        type=float,
        default=0.01,
        help="Joint std threshold in radians (default: 0.01, ~0.6 degrees)"
    )
    # Video validity parameters
    parser.add_argument(
        "--video-motion-threshold",
        type=float,
        default=1.0,
        help="Video motion threshold for frame difference (default: 1.0)"
    )
    parser.add_argument(
        "--video-sample-rate",
        type=int,
        default=5,
        help="Video sample rate - check every N frames (default: 5)"
    )
    parser.add_argument(
        "--video-max-samples",
        type=int,
        default=100,
        help="Maximum video frames to sample (default: 100)"
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"❌ Error: Input directory does not exist: {args.input}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("LeRobot Dataset Filter")
    print("=" * 60)
    print()

    try:
        report = filter_episodes(
            input_dir=args.input,
            output_dir=args.output,
            jump_threshold=args.jump_threshold,
            iqr_factor=args.iqr_factor,
            exclude_gripper=not args.include_gripper,
            use_symlink=not args.copy,
            joint_std_threshold=args.joint_std_threshold,
            video_motion_threshold=args.video_motion_threshold,
            video_sample_rate=args.video_sample_rate,
            video_max_samples=args.video_max_samples
        )

        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Total:  {report['summary']['total_episodes']}")
        print(f"  Passed: {report['summary']['passed']} ({100*report['summary']['passed']/report['summary']['total_episodes']:.1f}%)")
        print(f"  Failed: {report['summary']['total_episodes'] - report['summary']['passed']}")
        print()
        print("✅ Filtering complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
