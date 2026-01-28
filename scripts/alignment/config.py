"""
Configuration constants for alignment analysis.

This module provides backward-compatible exports while delegating
to the new robot_config module for actual configuration.

For new code, prefer using robot_config directly:
    from alignment.robot_config import get_robot_config
    config = get_robot_config("aloha")
"""

from .robot_config import (
    DEFAULT_CONFIG,
    get_robot_config,
)

# =============================================================================
# Backward Compatibility Exports
# =============================================================================

# Gripper dimension indices (from default config)
LEFT_GRIPPER_DIM = DEFAULT_CONFIG.gripper.left_dim
RIGHT_GRIPPER_DIM = DEFAULT_CONFIG.gripper.right_dim

# Default FPS
DEFAULT_FPS = DEFAULT_CONFIG.video.fps

# Legacy ROI_CONFIG format
ROI_CONFIG = {
    "default": {
        "wrist": {
            "y": DEFAULT_CONFIG.roi.wrist_y,
            "x": DEFAULT_CONFIG.roi.wrist_x,
        },
        "env": {
            "y": DEFAULT_CONFIG.roi.env_y,
            "x": DEFAULT_CONFIG.roi.env_x,
        },
        "full": {
            "y": DEFAULT_CONFIG.roi.full_y,
            "x": DEFAULT_CONFIG.roi.full_x,
        },
    },
    "aloha": {
        "wrist": {
            "y": get_robot_config("aloha").roi.wrist_y,
            "x": get_robot_config("aloha").roi.wrist_x,
        },
        "env": {
            "y": get_robot_config("aloha").roi.env_y,
            "x": get_robot_config("aloha").roi.env_x,
        },
        "full": {
            "y": get_robot_config("aloha").roi.full_y,
            "x": get_robot_config("aloha").roi.full_x,
        },
    },
}

# Legacy COLOR_THRESHOLD format
COLOR_THRESHOLD = {
    "orange": {
        "r_min": DEFAULT_CONFIG.color_threshold.orange_r_range[0],
        "r_max": DEFAULT_CONFIG.color_threshold.orange_r_range[1],
        "g_min": DEFAULT_CONFIG.color_threshold.orange_g_range[0],
        "g_max": DEFAULT_CONFIG.color_threshold.orange_g_range[1],
        "b_min": DEFAULT_CONFIG.color_threshold.orange_b_range[0],
        "b_max": DEFAULT_CONFIG.color_threshold.orange_b_range[1],
    },
    "black": {
        "max_value": DEFAULT_CONFIG.color_threshold.black_max_value,
    },
}

# Legacy ANALYSIS_CONFIG format
ANALYSIS_CONFIG = {
    "state_change_threshold": DEFAULT_CONFIG.analysis.state_change_threshold,
    "search_window": DEFAULT_CONFIG.analysis.search_window,
    "denoise_window": DEFAULT_CONFIG.analysis.denoise_window,
}


def get_roi_config(robot_type: str, camera: str) -> dict:
    """
    Get ROI configuration for given robot type and camera.

    DEPRECATED: Use get_robot_config(robot_type).roi.get_for_camera(camera)

    Args:
        robot_type: Robot type ("default", "aloha", "airbot_play", etc.)
        camera: Camera name

    Returns:
        ROI config dict with "y" and "x" ratios
    """
    config = get_robot_config(robot_type)
    return config.roi.get_for_camera(camera)
