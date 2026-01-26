#!/usr/bin/env python3
"""
Frame-State Alignment Analyzer

分析 LeRobot 数据集中 Frame（视频帧）与 State/Action（关节数据）的时间对齐情况。

详细文档请参考: docs/frame_state_alignment.md

使用方法:
    # 基本用法
    python scripts/analyze_frame_state_alignment.py <dataset_dir>

    # 使用黑色区域检测（ALOHA等黑色夹爪机器人）
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --black-detection

    # 使用颜色检测（橙色夹爪）
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --color-detection

    # 启用去噪
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --denoise

    # 分析所有episodes
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --all-episodes

完整可运行示例:
    # 分析单个episode（黑色检测+去噪）
    python scripts/analyze_frame_state_alignment.py /pfs/pfs-uaDOJM/home/maozan/code/data/0115_qz2_plant/merged --black-detection --denoise -o output/alignment_test/

    # 分析所有episodes并输出到指定目录
    python scripts/analyze_frame_state_alignment.py /pfs/pfs-uaDOJM/home/maozan/code/data/0115_qz2_plant/merged --black-detection --denoise --all-episodes -o output/alignment_all/
"""

import sys
from pathlib import Path

# Add scripts directory to path for module imports
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from alignment.cli import main

if __name__ == "__main__":
    sys.exit(main())
