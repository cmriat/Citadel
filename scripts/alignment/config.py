"""
Configuration constants for alignment analysis.
"""

# Gripper dimension indices in state array
LEFT_GRIPPER_DIM = 6
RIGHT_GRIPPER_DIM = 13

# Default FPS
DEFAULT_FPS = 25

# ROI (Region of Interest) configuration by robot type
# Format: {"y": (start_ratio, end_ratio), "x": (start_ratio, end_ratio)}
ROI_CONFIG = {
    "default": {
        "wrist": {"y": (0.60, 0.95), "x": (0.25, 0.75)},  # Tight ROI for gripper
        "env": {"y": (0.30, 0.90), "x": (0.20, 0.80)},    # Larger ROI for env camera
        "full": {"y": (0.40, 0.95), "x": (0.15, 0.85)},   # Default fallback
    },
    "aloha": {
        "wrist": {"y": (0.50, 1.00), "x": (0.20, 0.80)},  # ALOHA gripper at bottom
        "env": {"y": (0.30, 0.90), "x": (0.10, 0.90)},
        "full": {"y": (0.30, 0.90), "x": (0.10, 0.90)},
    },
}

# Color detection thresholds
COLOR_THRESHOLD = {
    "orange": {
        "r_min": 120, "r_max": 255,
        "g_min": 40, "g_max": 180,
        "b_min": 0, "b_max": 120,
    },
    "black": {
        "max_value": 80,  # Pixels below this are considered black
    },
}

# Analysis parameters
ANALYSIS_CONFIG = {
    "state_change_threshold": 0.01,  # Minimum state change to be significant
    "search_window": 5,              # Frames to search around state event
    "denoise_window": 10,            # Window size for denoising
}


def get_roi_config(robot_type: str, camera: str) -> dict:
    """
    Get ROI configuration for given robot type and camera.

    Args:
        robot_type: Robot type ("default", "aloha")
        camera: Camera name

    Returns:
        ROI config dict with "y" and "x" ratios
    """
    config = ROI_CONFIG.get(robot_type, ROI_CONFIG["default"])

    # Determine camera category
    if "wrist" in camera:
        return config["wrist"]
    elif camera in ["cam_env", "cam_high"]:
        return config["env"]
    else:
        return config["full"]
