"""
Frame-State Alignment Analysis Module

分析 LeRobot 数据集中 Frame（视频帧）与 State/Action（关节数据）的时间对齐情况。
"""

from .config import LEFT_GRIPPER_DIM, RIGHT_GRIPPER_DIM, ROI_CONFIG, COLOR_THRESHOLD
from .data_loader import DatasetLoader
from .video_tracker import VideoTracker
from .signal_processing import SignalProcessor
from .visualization import AlignmentVisualizer
from .analyzer import AlignmentAnalyzer, AlignmentResult, AlignmentReport

__all__ = [
    "LEFT_GRIPPER_DIM",
    "RIGHT_GRIPPER_DIM",
    "ROI_CONFIG",
    "COLOR_THRESHOLD",
    "DatasetLoader",
    "VideoTracker",
    "SignalProcessor",
    "AlignmentVisualizer",
    "AlignmentAnalyzer",
    "AlignmentResult",
    "AlignmentReport",
]
