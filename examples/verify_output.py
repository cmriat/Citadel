#!/usr/bin/env python3
"""验证 LeRobot v2.1 数据集格式"""

import argparse
import json
from pathlib import Path
import pyarrow.parquet as pq
import sys


def verify_dataset(dataset_path: str):
    """
    验证 LeRobot 数据集的完整性和正确性

    Args:
        dataset_path: 数据集根目录
    """
    dataset_dir = Path(dataset_path)

    if not dataset_dir.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return False

    print(f"\n{'='*60}")
    print(f"Verifying LeRobot v2.1 Dataset")
    print(f"{'='*60}")
    print(f"Path: {dataset_path}\n")

    all_passed = True

    # 1. 检查目录结构
    print("📁 Checking directory structure...")
    required_dirs = [
        dataset_dir / "data" / "chunk-000",
        dataset_dir / "videos" / "chunk-000",
        dataset_dir / "meta"
    ]

    for dir_path in required_dirs:
        if dir_path.exists():
            print(f"  ✓ {dir_path.relative_to(dataset_dir)}")
        else:
            print(f"  ✗ Missing: {dir_path.relative_to(dataset_dir)}")
            all_passed = False

    # 2. 检查元数据文件
    print("\n📄 Checking metadata files...")
    meta_dir = dataset_dir / "meta"

    required_meta = ["info.json", "episodes.jsonl", "tasks.jsonl"]
    for meta_file in required_meta:
        file_path = meta_dir / meta_file
        if file_path.exists():
            print(f"  ✓ {meta_file}")
        else:
            print(f"  ✗ Missing: {meta_file}")
            all_passed = False

    # 3. 验证 info.json
    print("\n📊 Verifying info.json...")
    info_file = meta_dir / "info.json"

    if info_file.exists():
        with open(info_file, 'r') as f:
            info = json.load(f)

        # 检查必需字段
        required_fields = [
            'codebase_version', 'total_episodes', 'total_frames',
            'total_tasks', 'total_videos', 'fps', 'features'
        ]

        for field in required_fields:
            if field in info:
                print(f"  ✓ {field}: {info[field] if field != 'features' else f'{len(info[field])} features'}")
            else:
                print(f"  ✗ Missing field: {field}")
                all_passed = False

        # 检查 features schema
        print("\n  Features:")
        expected_features = [
            'observation.state.slave',
            'observation.state.master',
            'action',
            'episode_index',
            'frame_index',
            'timestamp',
            'index',
            'next.done'
        ]

        for feat in expected_features:
            if feat in info['features']:
                feat_info = info['features'][feat]
                if 'dtype' in feat_info:
                    dtype = feat_info['dtype']
                    shape = feat_info.get('shape', 'N/A')
                    print(f"    ✓ {feat}: dtype={dtype}, shape={shape}")
                else:
                    print(f"    ✓ {feat}")
            else:
                print(f"    ✗ Missing: {feat}")
                all_passed = False

        # 显示相机信息
        if 'info' in info and 'cameras' in info['info']:
            cameras = info['info']['cameras']
            print(f"\n  Cameras: {', '.join(cameras)}")

    # 4. 检查 Parquet 文件
    print("\n📦 Checking Parquet files...")
    data_dir = dataset_dir / "data" / "chunk-000"
    parquet_files = sorted(data_dir.glob("episode_*.parquet"))

    if parquet_files:
        print(f"  Found {len(parquet_files)} episode files")

        # 验证第一个文件
        first_file = parquet_files[0]
        print(f"\n  Inspecting: {first_file.name}")

        try:
            table = pq.read_table(first_file)
            print(f"    ✓ Rows: {len(table)}")
            print(f"    ✓ Columns: {len(table.schema)}")

            # 显示 schema
            print("\n    Schema:")
            for field in table.schema:
                print(f"      - {field.name}: {field.type}")

            # 检查关键列
            required_cols = [
                'observation.state.slave',
                'observation.state.master',
                'action',
                'episode_index',
                'next.done'
            ]

            for col in required_cols:
                if col in table.column_names:
                    print(f"    ✓ Column exists: {col}")
                else:
                    print(f"    ✗ Missing column: {col}")
                    all_passed = False

        except Exception as e:
            print(f"    ✗ Error reading parquet: {e}")
            all_passed = False
    else:
        print("  ✗ No parquet files found")
        all_passed = False

    # 5. 检查视频文件
    print("\n🎥 Checking video files...")
    videos_dir = dataset_dir / "videos" / "chunk-000"

    if videos_dir.exists():
        camera_dirs = [d for d in videos_dir.iterdir() if d.is_dir()]
        print(f"  Found {len(camera_dirs)} camera directories")

        for cam_dir in camera_dirs:
            cam_name = cam_dir.name.replace("observation.images.", "")
            videos = sorted(cam_dir.glob("episode_*.mp4"))
            print(f"    ✓ {cam_name}: {len(videos)} videos")

            if len(videos) == 0:
                print(f"      ⚠ Warning: No videos found in {cam_name}")
    else:
        print("  ✗ Videos directory not found")
        all_passed = False

    # 6. 验证 episodes.jsonl
    print("\n📋 Checking episodes.jsonl...")
    episodes_file = meta_dir / "episodes.jsonl"

    if episodes_file.exists():
        episodes = []
        with open(episodes_file, 'r') as f:
            for line in f:
                episodes.append(json.loads(line))

        print(f"  ✓ Episodes recorded: {len(episodes)}")

        if episodes:
            print(f"\n  Sample (first episode):")
            print(f"    - episode_index: {episodes[0]['episode_index']}")
            print(f"    - length: {episodes[0]['length']}")
            print(f"    - tasks: {episodes[0]['tasks']}")

    # 7. 数据一致性检查
    print("\n🔍 Consistency checks...")

    try:
        if info_file.exists() and episodes_file.exists() and parquet_files:
            with open(info_file, 'r') as f:
                info = json.load(f)

            with open(episodes_file, 'r') as f:
                episodes = [json.loads(line) for line in f]

            # 检查 episode 数量
            if len(parquet_files) == len(episodes) == info['total_episodes']:
                print(f"  ✓ Episode count matches: {len(episodes)}")
            else:
                print(f"  ✗ Episode count mismatch:")
                print(f"    - info.json: {info['total_episodes']}")
                print(f"    - episodes.jsonl: {len(episodes)}")
                print(f"    - parquet files: {len(parquet_files)}")
                all_passed = False

            # 检查总帧数
            total_frames = sum(ep['length'] for ep in episodes)
            if total_frames == info['total_frames']:
                print(f"  ✓ Total frames match: {total_frames}")
            else:
                print(f"  ✗ Total frames mismatch:")
                print(f"    - info.json: {info['total_frames']}")
                print(f"    - episodes sum: {total_frames}")
                all_passed = False

    except Exception as e:
        print(f"  ✗ Consistency check failed: {e}")
        all_passed = False

    # 最终结果
    print(f"\n{'='*60}")
    if all_passed:
        print("✅ All checks passed! Dataset is valid.")
    else:
        print("⚠️  Some checks failed. Please review the errors above.")
    print(f"{'='*60}\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description='Verify LeRobot v2.1 dataset format'
    )
    parser.add_argument(
        '--dataset',
        type=str,
        required=True,
        help='Path to the dataset directory'
    )

    args = parser.parse_args()

    success = verify_dataset(args.dataset)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
