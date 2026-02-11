"""
Robot-specific configuration for alignment analysis.

Centralized configuration for all robot types, supporting:
- Gripper dimension indices and field names
- Camera naming conventions and suffixes
- Video format and path patterns
- ROI configuration for video tracking
- Color detection thresholds
- Analysis parameters

Usage:
    from alignment.robot_config import get_robot_config

    config = get_robot_config("aloha")
    gripper_dim = config.get_gripper_dim("left")
    default_camera = config.get_default_camera()
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class GripperConfig:
    """Gripper dimension and field configuration."""

    left_dim: int = 6
    right_dim: int = 13
    left_field: str = "left_gripper"
    right_field: str = "right_gripper"


@dataclass(frozen=True)
class CameraConfig:
    """Camera naming and configuration."""

    left_wrist: str = "cam_left_wrist"
    right_wrist: str = "cam_right_wrist"
    env: str = "cam_env"
    # Camera name suffix (e.g., "_rgb" for galaxea_r1_lite)
    suffix: str = ""

    def get_camera_name(self, camera_type: str) -> str:
        """
        Get full camera name with suffix.

        Args:
            camera_type: One of "left_wrist", "right_wrist", "env"
                        or a direct camera name

        Returns:
            Full camera name with suffix applied
        """
        # Try to get predefined camera name
        base = getattr(self, camera_type, camera_type)
        return f"{base}{self.suffix}" if self.suffix else base

    def get_default_camera(self) -> str:
        """Get default camera (left wrist) with suffix."""
        return self.get_camera_name("left_wrist")


@dataclass(frozen=True)
class VideoConfig:
    """Video format and path configuration."""

    fps: float = 25.0
    resolution: tuple[int, int] = (224, 224)  # (height, width)
    # Path pattern with placeholders: {chunk}, {camera}, {episode}, {file}
    path_pattern: str = "videos/chunk-{chunk:03d}/observation.images.{camera}/episode_{episode:06d}.mp4"
    # Alternative patterns for fallback (tried in order)
    fallback_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class ROIConfig:
    """Region of Interest configuration for video tracking."""

    # ROI for wrist cameras (typically contains gripper)
    wrist_y: tuple[float, float] = (0.60, 0.95)
    wrist_x: tuple[float, float] = (0.25, 0.75)
    # ROI for environment cameras
    env_y: tuple[float, float] = (0.30, 0.90)
    env_x: tuple[float, float] = (0.20, 0.80)
    # Full frame ROI (fallback)
    full_y: tuple[float, float] = (0.40, 0.95)
    full_x: tuple[float, float] = (0.15, 0.85)

    def get_for_camera(self, camera: str) -> dict[str, tuple[float, float]]:
        """
        Get ROI config based on camera name.

        Args:
            camera: Camera name

        Returns:
            Dict with "y" and "x" ratio tuples
        """
        # Wrist cameras: contains "wrist" or is "handeye" (Franka wrist camera)
        if "wrist" in camera or camera == "handeye":
            return {"y": self.wrist_y, "x": self.wrist_x}
        elif any(env_name in camera for env_name in ["cam_env", "cam_high", "main", "side"]):
            return {"y": self.env_y, "x": self.env_x}
        return {"y": self.full_y, "x": self.full_x}


@dataclass(frozen=True)
class ColorThresholdConfig:
    """Color detection threshold configuration."""

    # Orange detection (for orange grippers like airbot_play)
    orange_r_range: tuple[int, int] = (120, 255)
    orange_g_range: tuple[int, int] = (40, 180)
    orange_b_range: tuple[int, int] = (0, 120)
    # Black detection (for dark grippers like aloha)
    black_max_value: int = 80
    # Custom color detection ROI (for ColorTracker)
    color_roi_y: tuple[float, float] = (0.5, 1.0)


@dataclass(frozen=True)
class AnalysisConfig:
    """Analysis parameters configuration."""

    state_change_threshold: float = 0.01  # Minimum state change to be significant
    search_window: int = 5  # Frames to search around state event
    denoise_window: int = 10  # Window size for denoising


@dataclass
class RobotConfig:
    """
    Complete robot-specific configuration.

    Aggregates all configuration aspects for a specific robot type.
    """

    name: str

    gripper: GripperConfig = field(default_factory=GripperConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    roi: ROIConfig = field(default_factory=ROIConfig)
    color_threshold: ColorThresholdConfig = field(default_factory=ColorThresholdConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)

    def get_gripper_dim(self, side: Literal["left", "right"]) -> int:
        """Get gripper dimension index for specified side."""
        return self.gripper.left_dim if side == "left" else self.gripper.right_dim

    def get_gripper_field(self, side: Literal["left", "right"]) -> str:
        """Get gripper field name for specified side."""
        return self.gripper.left_field if side == "left" else self.gripper.right_field

    def get_default_camera(self) -> str:
        """Get default camera name with suffix."""
        return self.camera.get_default_camera()


# =============================================================================
# Pre-defined Robot Configurations
# =============================================================================

AIRBOT_PLAY_CONFIG = RobotConfig(
    name="airbot_play",
    gripper=GripperConfig(
        left_dim=6,
        right_dim=13,
        left_field="left_gripper",
        right_field="right_gripper",
    ),
    camera=CameraConfig(
        left_wrist="cam_left_wrist",
        right_wrist="cam_right_wrist",
        env="cam_env",
        suffix="",
    ),
    video=VideoConfig(
        fps=25.0,
        resolution=(224, 224),
        path_pattern="videos/chunk-{chunk:03d}/observation.images.{camera}/episode_{episode:06d}.mp4",
    ),
    roi=ROIConfig(
        wrist_y=(0.60, 0.95),
        wrist_x=(0.25, 0.75),
        env_y=(0.30, 0.90),
        env_x=(0.20, 0.80),
        full_y=(0.40, 0.95),
        full_x=(0.15, 0.85),
    ),
)

ALOHA_CONFIG = RobotConfig(
    name="aloha",
    gripper=GripperConfig(
        left_dim=6,
        right_dim=13,
        left_field="left_gripper",
        right_field="right_gripper",
    ),
    camera=CameraConfig(
        left_wrist="cam_left_wrist",
        right_wrist="cam_right_wrist",
        env="cam_high",
        suffix="",
    ),
    video=VideoConfig(
        fps=50.0,
        resolution=(480, 640),
        path_pattern="videos/observation.images.{camera}/chunk-{chunk:03d}/file-{file:03d}.mp4",
    ),
    roi=ROIConfig(
        wrist_y=(0.50, 1.00),
        wrist_x=(0.20, 0.80),
        env_y=(0.30, 0.90),
        env_x=(0.10, 0.90),
        full_y=(0.30, 0.90),
        full_x=(0.10, 0.90),
    ),
)

GALAXEA_R1_LITE_CONFIG = RobotConfig(
    name="galaxea_r1_lite",
    gripper=GripperConfig(
        left_dim=6,
        right_dim=13,
        left_field="left_gripper_open",
        right_field="right_gripper_open",
    ),
    camera=CameraConfig(
        left_wrist="cam_left_wrist",
        right_wrist="cam_right_wrist",
        env="cam_high",
        suffix="_rgb",
    ),
    video=VideoConfig(
        fps=30.0,
        resolution=(720, 1280),
        path_pattern="chunk-{chunk:03d}/observation.images.{camera}/episode_{episode:06d}.mp4",
        fallback_patterns=(
            "videos/chunk-{chunk:03d}/observation.images.{camera}/episode_{episode:06d}.mp4",
        ),
    ),
    roi=ROIConfig(
        wrist_y=(0.55, 0.95),
        wrist_x=(0.20, 0.80),
        env_y=(0.25, 0.85),
        env_x=(0.15, 0.85),
        full_y=(0.35, 0.90),
        full_x=(0.15, 0.85),
    ),
)

# Franka single-arm robot configuration (for data with observation.images.xxx camera naming)
# Note: Camera names should NOT include "observation.images." prefix - it's added by data_loader
FRANKA_CONFIG = RobotConfig(
    name="franka",
    gripper=GripperConfig(
        left_dim=7,  # Single gripper at dimension 7 (8th dimension, 0-indexed)
        right_dim=7,  # Same as left since it's single arm
        left_field="gripper",
        right_field="gripper",
    ),
    camera=CameraConfig(
        left_wrist="handeye",  # Will become "observation.images.handeye"
        right_wrist="handeye",
        env="main",
        suffix="",
    ),
    video=VideoConfig(
        fps=30.0,
        resolution=(480, 640),
        path_pattern="videos/chunk-{chunk:03d}/observation.images.{camera}/episode_{episode:06d}.mp4",
    ),
    roi=ROIConfig(
        wrist_y=(0.60, 0.95),
        wrist_x=(0.25, 0.75),
        env_y=(0.30, 0.90),
        env_x=(0.20, 0.80),
        full_y=(0.40, 0.95),
        full_x=(0.15, 0.85),
    ),
)

# RoboTwin Agilex ALOHA simulation configuration
ROBOTWIN_ALOHA_AGILEX_CONFIG = RobotConfig(
    name="robotwin_aloha_agilex",
    gripper=GripperConfig(
        left_dim=6,  # left_gripper at index 6
        right_dim=13,  # right_gripper at index 13
        left_field="left_gripper",
        right_field="right_gripper",
    ),
    camera=CameraConfig(
        left_wrist="cam_left_wrist",
        right_wrist="cam_right_wrist",
        env="cam_high",
        suffix="",
    ),
    video=VideoConfig(
        fps=20.0,  # Simulation runs at 20 FPS
        resolution=(480, 640),
        path_pattern="videos/chunk-{chunk:03d}/observation.images.{camera}/episode_{episode:06d}.mp4",
    ),
    roi=ROIConfig(
        wrist_y=(0.50, 1.00),  # Simulation may have different gripper positions
        wrist_x=(0.20, 0.80),
        env_y=(0.30, 0.90),
        env_x=(0.10, 0.90),
        full_y=(0.30, 0.90),
        full_x=(0.10, 0.90),
    ),
)

# Default configuration (used as fallback)
DEFAULT_CONFIG = AIRBOT_PLAY_CONFIG


# =============================================================================
# Robot Configuration Registry
# =============================================================================

_ROBOT_REGISTRY: dict[str, RobotConfig] = {
    "default": DEFAULT_CONFIG,
    "airbot_play": AIRBOT_PLAY_CONFIG,
    "aloha": ALOHA_CONFIG,
    "galaxea_r1_lite": GALAXEA_R1_LITE_CONFIG,
    "franka": FRANKA_CONFIG,
    "robotwin_aloha_agilex": ROBOTWIN_ALOHA_AGILEX_CONFIG,
}


def get_robot_config(robot_type: str) -> RobotConfig:
    """
    Get robot configuration by type name.

    Args:
        robot_type: Robot type identifier (e.g., "aloha", "airbot_play")

    Returns:
        RobotConfig for the specified robot type, or default if not found
    """
    return _ROBOT_REGISTRY.get(robot_type, DEFAULT_CONFIG)


def register_robot_config(robot_type: str, config: RobotConfig) -> None:
    """
    Register a new robot configuration.

    Args:
        robot_type: Robot type identifier
        config: RobotConfig instance
    """
    _ROBOT_REGISTRY[robot_type] = config


def list_robot_types() -> list[str]:
    """List all registered robot types."""
    return list(_ROBOT_REGISTRY.keys())
