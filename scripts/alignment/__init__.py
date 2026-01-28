"""
Frame-State Alignment Analysis Module

分析 LeRobot 数据集中 Frame（视频帧）与 State/Action（关节数据）的时间对齐情况。
"""

# Robot configuration (new)
from .robot_config import (
    RobotConfig,
    GripperConfig,
    CameraConfig,
    VideoConfig,
    ROIConfig,
    ColorThresholdConfig,
    AnalysisConfig,
    get_robot_config,
    register_robot_config,
    list_robot_types,
    DEFAULT_CONFIG,
    AIRBOT_PLAY_CONFIG,
    ALOHA_CONFIG,
    GALAXEA_R1_LITE_CONFIG,
)

# Legacy exports (for backward compatibility)
from .config import LEFT_GRIPPER_DIM, RIGHT_GRIPPER_DIM, ROI_CONFIG, COLOR_THRESHOLD

# Core components
from .data_loader import DatasetLoader
from .video_tracker import VideoTracker
from .signal_processing import SignalProcessor
from .visualization import AlignmentVisualizer
from .analyzer import AlignmentAnalyzer, AlignmentResult, AlignmentReport

__all__ = [
    # Robot configuration (new)
    "RobotConfig",
    "GripperConfig",
    "CameraConfig",
    "VideoConfig",
    "ROIConfig",
    "ColorThresholdConfig",
    "AnalysisConfig",
    "get_robot_config",
    "register_robot_config",
    "list_robot_types",
    "DEFAULT_CONFIG",
    "AIRBOT_PLAY_CONFIG",
    "ALOHA_CONFIG",
    "GALAXEA_R1_LITE_CONFIG",
    # Legacy exports
    "LEFT_GRIPPER_DIM",
    "RIGHT_GRIPPER_DIM",
    "ROI_CONFIG",
    "COLOR_THRESHOLD",
    # Core components
    "DatasetLoader",
    "VideoTracker",
    "SignalProcessor",
    "AlignmentVisualizer",
    "AlignmentAnalyzer",
    "AlignmentResult",
    "AlignmentReport",
]
