#!/usr/bin/env python3
"""
Frame-State Alignment Analyzer

分析 LeRobot 数据集中 Frame（视频帧）与 State/Action（关节数据）的时间对齐情况。
支持多种机器人类型，自动检测数据集配置。

详细文档请参考: docs/frame_state_alignment.md

支持的机器人类型:
    - airbot_play: 默认机器人，橙色夹爪，25 FPS，相机名 cam_left_wrist
    - aloha: ALOHA 机器人，黑色夹爪，50 FPS，相机名 cam_left_wrist
    - galaxea_r1_lite: Galaxea R1 Lite，30 FPS，相机名带 _rgb 后缀

使用方法:
    # 基本用法（自动检测机器人类型）
    python scripts/analyze_frame_state_alignment.py <dataset_dir>

    # 手动指定机器人类型（覆盖自动检测）
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --robot-type aloha

    # 使用黑色区域检测（ALOHA 等黑色夹爪机器人）
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --black-detection

    # 使用颜色检测（橙色夹爪）
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --color-detection

    # 启用去噪
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --denoise

    # 分析所有 episodes
    python scripts/analyze_frame_state_alignment.py <dataset_dir> --all-episodes

完整可运行示例:
    # airbot_play (qz2_plant) - 自动检测
    python scripts/analyze_frame_state_alignment.py \\
        /pfs/pfs-uaDOJM/home/maozan/code/data/0115_qz2_plant/merged \\
        -e 0 -o output/alignment_airbot/

    # aloha (aloha_mobile_cabinet) - 黑色检测模式
    python scripts/analyze_frame_state_alignment.py \\
        /pfs/pfs-uaDOJM/home/maozan/code/data/opensource/aloha_mobile_cabinet \\
        -e 0 --black-detection -o output/alignment_aloha/

    # galaxea_r1_lite (R1_lite_make_a_landline_call) - 自动检测相机后缀
    python scripts/analyze_frame_state_alignment.py \\
        /pfs/pfs-uaDOJM/home/maozan/code/data/opensource/R1_lite_make_a_landline_call \\
        -e 0 -o output/alignment_r1_lite/

    # 分析所有 episodes 并启用去噪
    python scripts/analyze_frame_state_alignment.py <dataset_dir> \\
        --all-episodes --denoise -o output/alignment_all/
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
