"""
Video tracking module for gripper motion detection.

Supports multiple tracking methods:
- ROI: Gray frame difference in region of interest
- Black: Black region detection for dark grippers
- Color: Orange color detection for orange grippers
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

import av
import numpy as np

from .robot_config import get_robot_config


class BaseTracker(ABC):
    """Abstract base class for video trackers."""

    @abstractmethod
    def compute_diffs(self, video_path: Path, frame_range: tuple[int, int]) -> np.ndarray:
        """Compute frame differences."""
        pass


class ROITracker(BaseTracker):
    """ROI-based gray frame difference tracker."""

    def __init__(self, robot_type: str = "default", camera: str = None):
        config = get_robot_config(robot_type)
        # Use default camera from robot config if not specified
        camera = camera or config.get_default_camera()
        roi_config = config.roi.get_for_camera(camera)
        self.roi_y = roi_config["y"]
        self.roi_x = roi_config["x"]

    def compute_diffs(self, video_path: Path, frame_range: tuple[int, int] = (0, -1)) -> np.ndarray:
        container = av.open(str(video_path))
        stream = container.streams.video[0]

        prev_roi = None
        diffs = []
        frame_idx = 0
        start_frame, end_frame = frame_range

        for frame in container.decode(stream):
            if frame_idx < start_frame:
                frame_idx += 1
                continue
            if end_frame != -1 and frame_idx > end_frame:
                break

            img = frame.to_ndarray(format="gray").astype(np.float32)
            h, w = img.shape

            # Extract ROI
            y_start, y_end = int(h * self.roi_y[0]), int(h * self.roi_y[1])
            x_start, x_end = int(w * self.roi_x[0]), int(w * self.roi_x[1])
            roi = img[y_start:y_end, x_start:x_end]

            if prev_roi is not None:
                diff = np.abs(roi - prev_roi).mean()
                diffs.append(diff)
            else:
                diffs.append(0)

            prev_roi = roi
            frame_idx += 1

        container.close()
        return np.array(diffs)


class BlackRegionTracker(BaseTracker):
    """Black region detection tracker for dark grippers."""

    def __init__(self, robot_type: str = "default", camera: str = None,
                 threshold: int = None):
        config = get_robot_config(robot_type)
        # Use default camera from robot config if not specified
        camera = camera or config.get_default_camera()
        roi_config = config.roi.get_for_camera(camera)
        self.roi_y = roi_config["y"]
        self.roi_x = roi_config["x"]
        self.threshold = threshold or config.color_threshold.black_max_value

    def compute_diffs(self, video_path: Path, frame_range: tuple[int, int] = (0, -1)) -> np.ndarray:
        container = av.open(str(video_path))
        stream = container.streams.video[0]

        prev_mask = None
        diffs = []
        frame_idx = 0
        start_frame, end_frame = frame_range

        for frame in container.decode(stream):
            if frame_idx < start_frame:
                frame_idx += 1
                continue
            if end_frame != -1 and frame_idx > end_frame:
                break

            img = frame.to_ndarray(format="gray")
            h, w = img.shape

            # Extract ROI
            y_start, y_end = int(h * self.roi_y[0]), int(h * self.roi_y[1])
            x_start, x_end = int(w * self.roi_x[0]), int(w * self.roi_x[1])
            roi = img[y_start:y_end, x_start:x_end]

            # Detect black regions
            black_mask = (roi < self.threshold).astype(np.float32)

            if prev_mask is not None:
                diff = np.abs(black_mask - prev_mask).mean()
                diffs.append(diff)
            else:
                diffs.append(0)

            prev_mask = black_mask
            frame_idx += 1

        container.close()
        return np.array(diffs)


class ColorTracker(BaseTracker):
    """Orange color detection tracker - now robot-aware."""

    def __init__(self, robot_type: str = "default", camera: str = None):
        config = get_robot_config(robot_type)
        # Use robot-specific color ROI
        self.roi_y = config.color_threshold.color_roi_y
        # Use robot-specific color thresholds
        ct = config.color_threshold
        self.color_config = {
            "r_min": ct.orange_r_range[0],
            "r_max": ct.orange_r_range[1],
            "g_min": ct.orange_g_range[0],
            "g_max": ct.orange_g_range[1],
            "b_min": ct.orange_b_range[0],
            "b_max": ct.orange_b_range[1],
        }

    def compute_diffs(self, video_path: Path, frame_range: tuple[int, int] = (0, -1)) -> np.ndarray:
        container = av.open(str(video_path))
        stream = container.streams.video[0]

        prev_mask = None
        diffs = []
        frame_idx = 0
        start_frame, end_frame = frame_range

        for frame in container.decode(stream):
            if frame_idx < start_frame:
                frame_idx += 1
                continue
            if end_frame != -1 and frame_idx > end_frame:
                break

            img = frame.to_ndarray(format="rgb24").astype(np.float32)
            h, _w = img.shape[:2]

            # Focus on configured region
            roi = img[int(h * self.roi_y[0]):int(h * self.roi_y[1]), :]
            r, g, b = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]

            # Orange detection
            c = self.color_config
            orange_mask = (
                (r > c["r_min"]) &
                (g > c["g_min"]) & (g < c["g_max"]) &
                (b < c["b_max"]) &
                (r > g) & (g > b)
            ).astype(np.float32)

            if prev_mask is not None:
                diff = np.abs(orange_mask - prev_mask).mean()
                diffs.append(diff)
            else:
                diffs.append(0)

            prev_mask = orange_mask
            frame_idx += 1

        container.close()
        return np.array(diffs)


class VideoTracker:
    """
    Unified video tracker interface.

    Factory class that creates appropriate tracker based on method.
    """

    METHODS = Literal["roi", "black", "color"]

    def __init__(self, method: str = "roi", robot_type: str = "default",
                 camera: str = None):
        self.method = method
        self.robot_type = robot_type
        self.camera = camera
        self._tracker = self._create_tracker()

    def _create_tracker(self) -> BaseTracker:
        """Create tracker instance based on method."""
        if self.method == "roi":
            return ROITracker(self.robot_type, self.camera)
        elif self.method == "black":
            return BlackRegionTracker(self.robot_type, self.camera)
        elif self.method == "color":
            return ColorTracker(self.robot_type, self.camera)
        else:
            raise ValueError(f"Unknown tracking method: {self.method}")

    def compute_diffs(self, video_path: Path, frame_range: tuple[int, int] = (0, -1)) -> np.ndarray:
        """Compute frame differences using the configured tracker."""
        return self._tracker.compute_diffs(video_path, frame_range)

    @property
    def description(self) -> str:
        """Human-readable description of tracking method."""
        descriptions = {
            "roi": f"ROI-based frame diff ({self.robot_type} gripper region)",
            "black": f"Black region detection ({self.robot_type})",
            "color": f"Orange color tracking ({self.robot_type})",
        }
        return descriptions.get(self.method, self.method)
